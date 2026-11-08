"""Operator-controlled fleet scan/contact jobs. Never auto-decides or writes Yext."""

from __future__ import annotations
import copy
import threading
import time
from pathlib import Path
from .storage import StateStore
from .errors import AppError
from .domain import parse_dt, is_proposal_active


BATCH_SIZE = 100


class FleetRunner:
    def __init__(self, service):
        self.service = service
        self.s = service
        self.state = StateStore(str(Path(service.state_dir) / "fleet.json"))
        self.lock = self.state.lock
        self.stop = threading.Event()
        self.thread = None
        self.active = False
        changed = False
        for j in self.state.data["jobs"].values():
            if j["status"] == "RUNNING":
                j["status"] = "INTERRUPTED"
                changed = True
            if j["contact_status"] == "RUNNING":
                j["contact_status"] = "INTERRUPTED"
                changed = True
        if changed:
            self.state.save()

    def _public(self, j):
        return copy.deepcopy({k: v for k, v in j.items() if not k.startswith("_")})

    def get(self, jid=None):
        with self.lock:
            if jid is None:
                jobs = list(self.state.data["jobs"].values())
                return {
                    "run": self._public(jobs[-1]) if jobs else None,
                    "total_businesses": len(self.s.data.contacts),
                    "mode": self.s.mode,
                }
            j = self.state.get("jobs", jid)
            if not j:
                raise AppError(404, "RUN_NOT_FOUND", "Fleet run not found.")
            return self._public(j)

    def _update(self, jid, **values):
        with self.lock:
            self.state.get("jobs", jid).update(values)
            self.state.save()

    def _launch(self, fn, *args):
        self.active = True

        def work():
            try:
                fn(*args)
            except Exception as e:
                jid = args[0]
                stage = "contact_status" if fn.__name__ == "_contacts" else "status"
                self._update(
                    jid,
                    **{stage: "FAILED", "error_code": getattr(e, "code", "JOB_FAILED")},
                )
            finally:
                self.active = False

        self.thread = threading.Thread(target=work, daemon=True, name="fleet")
        self.thread.start()

    def start(self, body):
        if self.s.mode != "mock":
            raise AppError(
                409,
                "MOCK_ONLY",
                "Fleet demonstration runs in mock mode; sandbox is mapped to one entity.",
            )
        with self.lock:
            if self.active:
                raise AppError(
                    409, "RUN_ACTIVE", "A fleet operation is already running."
                )
            with self.s.lock:
                self.s._refresh_sources()
            ids = sorted(self.s.data.contacts)
            jid = self.state.next_id("fleet")
            j = {
                "run_id": jid,
                "status": "RUNNING",
                "scope": body["scope"],
                "date": body.get("date"),
                "total_businesses": len(ids),
                "processed_businesses": 0,
                "failed_businesses": 0,
                "case_count": 0,
                "counts": {"SUGGEST": 0, "FLAG": 0, "NO_ACTION": 0},
                "business_counts": {"SUGGEST": 0, "FLAG": 0, "NO_ACTION": 0},
                "ready_proposals": 0,
                "ready_businesses": 0,
                "contact_status": "NOT_PREPARED",
                "contact_mode": None,
                "contact_counts": {},
                "contact_processed": 0,
                "started_at": self.s.stamp(),
                "completed_at": None,
                "elapsed_seconds": 0,
                "error_code": None,
                "errors": [],
                "_case_ids": [],
                "_contact_ids": [],
            }
            self.state.put("jobs", jid, j)
            self.state.save()
            self._launch(self._scan, jid, ids, body)
            return self._public(j)

    def _scan(self, jid, ids, body):
        started = time.monotonic()
        # Optimization: Fetch a single paginated bulk snapshot of entity states upfront
        # rather than performing thousands of individual HTTP GET requests for each business entity.
        snapshot = {e["meta"]["id"]: e for e in self.s.client.list_entities(limit=BATCH_SIZE)}
        counts = {"SUGGEST": 0, "FLAG": 0, "NO_ACTION": 0}
        businesses = {k: set() for k in counts}
        case_ids = []
        errors = []
        processed = 0
        failed = 0
        for start in range(0, len(ids), BATCH_SIZE):
            if self.stop.is_set():
                self._update(jid, status="INTERRUPTED")
                return
            batch = ids[start : start + BATCH_SIZE]
            valid = [eid for eid in batch if eid in snapshot]
            for eid in batch:
                if eid not in snapshot:
                    errors.append({"entity_id": eid, "code": "LIVE_ENTITY_MISSING"})
                    failed += 1
            request = {
                "scope": "OPERATIONAL"
                if body["scope"] == "OPERATIONAL"
                else "EXPLICIT_DATES",
                "entity_ids": valid,
            }
            if body["scope"] == "EXPLICIT_DATE":
                request["dates"] = [body["date"]]
            if valid:
                # Batch holds the normal service lock; releases it between batches.
                result = self.s.cycle(
                    request, apply_permissions=False, live_entities=snapshot
                )
                case_ids.extend(result["case_ids"])
                with self.s.lock:
                    for cid in result["case_ids"]:
                        c = self.s.store.get("cases", cid)
                        counts[c["action"]] += 1
                        businesses[c["action"]].add(c["entity_id"])
            processed += len(batch)
            ready = []
            with self.s.lock:
                now = self.s.now()
                for cid in case_ids:
                    c = self.s.store.get("cases", cid)
                    p = self.s.store.get("proposals", c.get("proposal_id", ""))
                    if p and is_proposal_active(p, now):
                        ready.append(p)
            self._update(
                jid,
                processed_businesses=processed,
                failed_businesses=failed,
                case_count=len(case_ids),
                counts=counts,
                business_counts={k: len(v) for k, v in businesses.items()},
                ready_proposals=len(ready),
                ready_businesses=len({p["entity_id"] for p in ready}),
                errors=errors[:BATCH_SIZE],
                _case_ids=case_ids,
                elapsed_seconds=round(time.monotonic() - started, 1),
            )
        self._update(
            jid,
            status="COMPLETED_WITH_ERRORS" if failed else "COMPLETED",
            completed_at=self.s.stamp(),
        )

    def prepare_contacts(self, jid, body):
        with self.lock:
            j = self.state.get("jobs", jid)
            if not j:
                raise AppError(404, "RUN_NOT_FOUND", "Fleet run not found.")
            if self.active:
                raise AppError(
                    409, "RUN_ACTIVE", "A fleet operation is already running."
                )
            if j["status"] not in ("COMPLETED", "COMPLETED_WITH_ERRORS"):
                raise AppError(409, "SCAN_NOT_COMPLETE", "Complete a scan first.")
            mode = body["delivery_mode"]
            if j["contact_status"] == "COMPLETED" and j["contact_mode"] == mode:
                return self._public(j)
            j.update(
                contact_status="RUNNING",
                contact_mode=mode,
                contact_processed=0,
                contact_counts={},
                error_code=None,
            )
            self.state.save()
            self._launch(self._contacts, jid, mode)
            return self._public(j)

    def _contacts(self, jid, mode):
        with self.lock:
            case_ids = list(self.state.get("jobs", jid)["_case_ids"])
        groups = {}
        with self.s.lock:
            for cid in case_ids:
                c = self.s.store.get("cases", cid)
                p = (
                    self.s.store.get("proposals", c.get("proposal_id", ""))
                    if c
                    else None
                )
                if p and is_proposal_active(p, self.s.now()):
                    groups.setdefault(p["entity_id"], []).append(p["proposal_id"])
        counts = {}
        message_ids = []
        done = 0
        entries = list(groups.items())
        for start in range(0, len(entries), BATCH_SIZE):
            if self.stop.is_set():
                self._update(jid, contact_status="INTERRUPTED")
                return
            with self.s.lock:
                for eid, pids in entries[start : start + BATCH_SIZE]:
                    # Revalidate proposals inside create_message; honor opt-out/pause.
                    try:
                        m = self.s.create_message(
                            {
                                "entity_id": eid,
                                "proposal_ids": pids,
                                "delivery_mode": mode,
                            },
                            persist=False,
                            include_entry=False,
                        )
                        counts[m["status"]] = counts.get(m["status"], 0) + 1
                        message_ids.append(m["message_id"])
                    except AppError as e:
                        if e.status not in (409, 410):
                            raise
                        counts["SKIPPED_CHANGED"] = counts.get("SKIPPED_CHANGED", 0) + 1
                    done += 1
                self.s.store.save()
            self._update(
                jid,
                contact_counts=counts,
                contact_processed=done,
                _contact_ids=message_ids,
            )
        self._update(jid, contact_status="COMPLETED")

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
