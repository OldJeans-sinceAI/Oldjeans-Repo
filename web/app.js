const APP_BASE = location.pathname === "/sandbox" || location.pathname.startsWith("/sandbox/") ? "/sandbox" : "";
const IS_OWNER = location.pathname.startsWith(APP_BASE + "/customer");
const OWNER_STORAGE = "connect-owner" + APP_BASE;
"use strict";
const words = {
  en: {
    workspace: "WORKSPACE",
    demo: "Guided demo",
    overview: "Workspace",
    inbox: "Inbox",
    staff: "Staff review",
    platform: "Business information",
    tag: "BUSINESS HOURS, IN SYNC",
    title: "Good hours. Better visits.",
    intro:
      "Turn reliable evidence into the right opening hours. Give every owner a clear choice.",
    mock: "SIMULATED CONTACT",
    sandbox: "SANDBOX · SIMULATED CONTACT",
    clock: "Demo clock",
    suggest: "Suggestions",
    flag: "Needs a closer look",
    no_action: "No outreach needed",
    runTitle: "Inspect one business · demo",
    search: "Find a business",
    searchHint: "Search name or ID…",
    business: "Business",
    date: "Target date",
    run: "Detect & suggest",
    examples: "Try a scenario",
    history: "Holiday history",
    closure: "Closure concern",
    correct: "Already correct",
    limited: "No history",
    detect: "Detect",
    suggestStep: "Suggest",
    contact: "Contact",
    decide: "Decide",
    apply: "Apply & confirm",
    queue: "Your review queue",
    all: "All cases",
    export: "Download CSV",
    businessCol: "Business / date",
    action: "Action",
    reason: "Reason",
    priority: "Priority",
    details: "View details",
    emptyTitle: "A little evidence goes a long way.",
    emptyText:
      "Choose a business and a date above. We’ll check the evidence before recommending a change.",
    safety:
      "Original data stays intact. Changes apply only after an authorized decision. Publisher timing is estimated from the supplied mock listings.",
    connected: "Connected to the local demo",
    brandSub: "by OldJeans",
    sideTitle: "The right hours, everywhere.",
    sideText: "Evidence first. Owner in control.",
    before: "Currently shown",
    after: "Suggested hours",
    confidence: "Evidence confidence",
    evidence: "Why this suggestion?",
    gaps: "What is still missing?",
    recheck: "Recheck when",
    close: "Close",
    preview: "Preview customer message",
    schedule: "Schedule message",
    noOutreach: "This case does not send a customer message.",
    noHistory:
      "Deferred does not mean confirmed correct. We’ll check again when relevant evidence becomes available.",
    resolve: "Record staff resolution",
    resolution: "Resolution",
    note: "Review notes",
    noteHint: "Explain your finding and the evidence reviewed.",
    resolved: "Resolved",
    needsOwner: "Needs owner review",
    dismissed: "Dismissed",
    save: "Save",
    saved: "Saved",
    previewReady: "Message preview is ready in the inbox.",
    queued: "Message scheduled",
    inboxTitle: "A clear conversation.",
    inboxIntro:
      "Preview the preferred channel and open the owner’s decision experience. Messages here are simulated.",
    emptyInbox: "No messages yet",
    emptyInboxText:
      "Open a suggestion and preview a message to begin the owner journey.",
    openCustomer: "Open owner view",
    channel: "Channel",
    status: "Status",
    scheduled: "Scheduled for",
    simulation: "Demo delivery · no message was sent to a real customer.",
    customerWelcome: "Your hours, your choice.",
    customerIntro:
      "Review the proposed change below. You can approve it, adjust it, or keep your current hours.",
    approve: "Approve hours",
    reject: "Keep current hours",
    edit: "Edit hours",
    editLabel: "Your opening hours",
    editHint: "Use 07:30-15:00, split intervals, or closed.",
    confirmEdit: "Confirm these hours",
    cancel: "Cancel",
    textLabel: "Or tell us in your own words",
    textHint: "For example: open 08:00-15:00",
    interpret: "Preview my reply",
    confirmReply: "Confirm this response",
    previewOnly: "This is a preview. Nothing changes until you confirm.",
    settings: "Your contact preferences",
    frequency: "How often should we contact you?",
    TWICE_MONTHLY: "Twice monthly · 1st & 15th",
    MONTHLY: "Monthly · 1st",
    PAUSED: "Paused",
    optout: "The source contact has opted out. Contact is blocked.",
    nextContact: "Next scheduled contact",
    permissionTitle: "Permission for future holiday corrections",
    permissionHelp:
      "Optional: allow validated corrections for this named holiday only. You can revoke this permission at any time.",
    grant: "Allow this holiday",
    revoke: "Revoke",
    permissionCheck:
      "I allow date-specific corrections for this holiday for up to one year.",
    result: "Your decision",
    verified: "Hours saved and checked.",
    rejected: "Current hours kept.",
    pending: "Decision received.",
    failed: "Your change needs attention.",
    resultExplain: "We read the hours back after saving to verify the change.",
    estimate: "Where will this appear?",
    estimateNote:
      "These are typical timings from the mock dataset, not confirmation of live publication.",
    unknown: "Timing unavailable",
    notStarted: "No update was requested.",
    refresh: "Refresh status",
    loading: "Loading…",
    busy: "Working…",
    error: "We couldn’t complete that request.",
    noSession: "Open this page from a customer message in the operator inbox.",
    returnHome: "Back to workspace",
    expired: "This proposal has expired. A fresh review is needed.",
    stale: "The proposal changed. Refresh before deciding.",
    unauthorized: "This session cannot access that business or proposal.",
    required: "Please complete the required fields.",
    dateInvalid: "Choose a future date for this demo.",
    limitedLabel: "Limited evidence",
    directLabel: "Direct evidence",
    partialLabel: "Partial evidence",
    URGENT: "Urgent",
    HIGH: "High",
    ROUTINE: "Routine",
    MEDIUM: "Medium",
    SUGGEST: "Suggest",
    FLAG: "Staff review",
    NO_ACTION: "No action",
    RETAIN: "Retain",
    DEFER: "Defer",
    STAFF_REVIEW: "Staff review",
    PROPOSAL_READY: "Proposal ready",
    PENDING: "Pending",
    APPROVED: "Approved",
    EDITED: "Edited",
    REJECTED: "Rejected",
    EXPIRED: "Expired",
    SUPERSEDED: "Superseded",
    STANDING_AUTHORIZED: "Standing permission",
    NOT_STARTED: "Not started",
    SCHEDULED: "Scheduled",
    SUCCEEDED: "Verified",
    FAILED: "Failed",
    CONFLICT: "Conflict",
    REVIEW_REQUIRED: "Review required",
    DELIVERED_SIMULATED: "Delivered · simulated",
    QUEUED: "Queued",
    BLOCKED_OPT_OUT: "Blocked · opted out",
    BLOCKED_PAUSED: "Blocked · paused",
    closed: "Closed",
    dates: "Affected dates",
    reviewSaved: "Staff review recorded",
    openEvidence: "Source references",
    permissionScope: "Scope",
    permissionExpiry: "Expires",
    editPreview: "Check your final change",
    sourceLanguage: "Demo messages are presented in English.",
    noProposal: "No active proposal is available.",
    bundle: "Each date has its own decision. Other dates stay unchanged.",
    emptyStaff: "No cases need staff review.",
    clockNote: "Simulated clock · 6 Nov 2026",
    readiness: "Checking connection…",
    retry: "Try again",
    runAll: "Operational review",
    allScope: "Review selected business through its next contact + 2 days",
  },
  ko: {
    workspace: "작업 공간",
    overview: "전체 보기",
    inbox: "메시지함",
    staff: "직원 검토",
    platform: "업체 정보 관리",
    tag: "근거로 연결하는 영업시간",
    title: "정확한 시간. 더 나은 방문.",
    intro:
      "신뢰할 수 있는 근거로 영업시간을 제안하고, 업주가 직접 결정하도록 돕습니다.",
    mock: "모의 연락",
    sandbox: "샌드박스 · 모의 연락",
    clock: "데모 시각",
    suggest: "제안 항목",
    flag: "직원 확인 필요",
    no_action: "연락하지 않는 항목",
    runTitle: "업체 한 곳 상세 확인 · 데모",
    search: "업체 검색",
    searchHint: "업체명 또는 ID 검색…",
    business: "업체",
    date: "대상 날짜",
    run: "탐지 · 제안 실행",
    examples: "시나리오 체험",
    history: "공휴일 이력",
    closure: "폐업 의심",
    correct: "현재 정보 적절",
    limited: "이력 없는 업체",
    detect: "탐지",
    suggestStep: "제안",
    contact: "연락",
    decide: "결정",
    apply: "적용 · 확인",
    queue: "검토할 항목",
    all: "전체",
    export: "CSV 다운로드",
    businessCol: "업체 / 날짜",
    action: "액션",
    reason: "판단 이유",
    priority: "중요도",
    details: "자세히 보기",
    emptyTitle: "작은 근거에서 정확한 판단으로.",
    emptyText:
      "업체와 날짜를 선택하세요. 변경을 제안하기 전에 관련 근거를 확인합니다.",
    safety:
      "원본 데이터는 보존됩니다. 권한이 확인된 결정 후에만 변경합니다. 게시 예상 시간은 제공된 모의 listings 데이터 기준입니다.",
    connected: "로컬 데모 연결됨",
    brandSub: "by OldJeans",
    sideTitle: "어디서나 정확한 영업시간.",
    sideText: "근거를 먼저, 결정은 업주에게.",
    before: "현재 표시 시간",
    after: "제안 시간",
    confidence: "근거 신뢰도",
    evidence: "이 시간을 제안하는 이유",
    gaps: "아직 부족한 정보",
    recheck: "다시 확인할 조건",
    close: "닫기",
    preview: "고객 메시지 미리보기",
    schedule: "메시지 예약",
    noOutreach: "이 항목은 고객에게 메시지를 보내지 않습니다.",
    noHistory:
      "보류는 현재 정보가 맞다는 뜻이 아닙니다. 관련 근거가 추가되면 다시 확인합니다.",
    resolve: "직원 검토 기록",
    resolution: "검토 결과",
    note: "검토 메모",
    noteHint: "확인한 내용과 근거를 남겨 주세요.",
    resolved: "해결",
    needsOwner: "업주 확인 필요",
    dismissed: "검토 종료",
    save: "저장",
    saved: "저장됨",
    previewReady: "메시지함에서 고객 메시지를 확인할 수 있습니다.",
    queued: "메시지 예약됨",
    inboxTitle: "이해하기 쉬운 대화.",
    inboxIntro:
      "선호 채널의 메시지를 확인하고 업주 결정 화면을 열어보세요. 이곳의 연락은 모의 실행입니다.",
    emptyInbox: "아직 메시지가 없습니다",
    emptyInboxText:
      "제안을 열고 고객 메시지를 미리보면 업주의 결정 흐름을 체험할 수 있습니다.",
    openCustomer: "업주 화면 열기",
    channel: "채널",
    status: "상태",
    scheduled: "예약 시각",
    simulation: "모의 발송 · 실제 고객에게 전송하지 않았습니다.",
    customerWelcome: "영업시간은 직접 결정하세요.",
    customerIntro:
      "제안 내용을 확인하고 승인하거나, 수정하거나, 현재 시간을 유지할 수 있습니다.",
    approve: "제안 승인",
    reject: "현재 시간 유지",
    edit: "시간 수정",
    editLabel: "원하는 영업시간",
    editHint: "07:30-15:00, 여러 구간 또는 closed를 입력하세요.",
    confirmEdit: "이 시간으로 확정",
    cancel: "취소",
    textLabel: "자연스러운 말로 답해도 됩니다",
    textHint: "예: 08:00-15:00으로 변경",
    interpret: "답변 미리보기",
    confirmReply: "이 답변 확정",
    previewOnly: "미리보기입니다. 확정하기 전에는 변경하지 않습니다.",
    settings: "연락 설정",
    frequency: "연락받을 주기",
    TWICE_MONTHLY: "월 2회 · 1일과 15일",
    MONTHLY: "월 1회 · 1일",
    PAUSED: "연락 일시 정지",
    optout: "원본 연락 정보에 수신 거부가 설정되어 있습니다.",
    nextContact: "다음 연락 예정",
    permissionTitle: "다음 공휴일 수정 권한",
    permissionHelp:
      "선택 사항: 해당 공휴일에 검증된 날짜별 수정만 허용합니다. 언제든 철회할 수 있습니다.",
    grant: "이 공휴일에 허용",
    revoke: "철회",
    permissionCheck: "해당 공휴일의 날짜별 수정을 최대 1년 동안 허용합니다.",
    result: "결정 결과",
    verified: "저장 후 다시 확인했습니다.",
    rejected: "현재 시간을 유지합니다.",
    pending: "결정을 접수했습니다.",
    failed: "변경 사항을 확인해야 합니다.",
    resultExplain: "변경을 저장한 뒤 다시 조회해 일치하는지 확인했습니다.",
    estimate: "어디에 반영되나요?",
    estimateNote:
      "모의 데이터의 일반적인 반영 시간입니다. 실제 게시 완료를 확인한 것은 아닙니다.",
    unknown: "반영 시간 확인 불가",
    notStarted: "변경을 요청하지 않았습니다.",
    refresh: "상태 새로고침",
    loading: "불러오는 중…",
    busy: "처리 중…",
    error: "요청을 완료하지 못했습니다.",
    noSession: "운영자 메시지함의 고객 메시지에서 이 화면을 열어 주세요.",
    returnHome: "작업 공간으로",
    expired: "제안의 유효기간이 지났습니다. 다시 검토해야 합니다.",
    stale: "제안이 변경되었습니다. 새로고침 후 결정해 주세요.",
    unauthorized: "이 세션에서는 해당 업체나 제안에 접근할 수 없습니다.",
    required: "필수 항목을 입력해 주세요.",
    dateInvalid: "데모 시각 이후의 날짜를 선택하세요.",
    limitedLabel: "근거 부족",
    directLabel: "직접 근거",
    partialLabel: "일부 근거",
    URGENT: "긴급",
    HIGH: "높음",
    ROUTINE: "보통",
    MEDIUM: "중간",
    SUGGEST: "제안",
    FLAG: "직원 검토",
    NO_ACTION: "액션 없음",
    RETAIN: "유지",
    DEFER: "보류",
    STAFF_REVIEW: "직원 검토",
    PROPOSAL_READY: "제안 준비",
    PENDING: "대기",
    APPROVED: "승인",
    EDITED: "수정 승인",
    REJECTED: "거절",
    EXPIRED: "만료",
    SUPERSEDED: "새 제안으로 대체",
    STANDING_AUTHORIZED: "사전 권한",
    NOT_STARTED: "미시작",
    SCHEDULED: "예약",
    SUCCEEDED: "저장 확인",
    FAILED: "실패",
    CONFLICT: "충돌",
    REVIEW_REQUIRED: "검토 필요",
    DELIVERED_SIMULATED: "모의 전달 완료",
    QUEUED: "예약 대기",
    BLOCKED_OPT_OUT: "수신 거부",
    BLOCKED_PAUSED: "연락 일시 정지",
    closed: "휴무",
    dates: "영향받는 날짜",
    reviewSaved: "직원 검토를 기록했습니다",
    openEvidence: "근거 출처",
    permissionScope: "허용 범위",
    permissionExpiry: "만료",
    editPreview: "최종 변경 내용 확인",
    sourceLanguage: "메시지는 업주가 선호하는 언어로 작성됩니다.",
    noProposal: "사용 가능한 제안이 없습니다.",
    bundle: "날짜마다 따로 결정합니다. 다른 날짜는 유지됩니다.",
    emptyStaff: "직원 검토가 필요한 항목이 없습니다.",
    clockNote: "모의 시각 · 2026년 11월 6일",
    readiness: "연결 확인 중…",
    retry: "다시 시도",
    runAll: "운영 범위 검토",
    allScope: "선택 업체의 다음 연락일 + 2일까지 검토",
  },
  fi: {
    workspace: "TYÖTILA",
    overview: "Yleiskuva",
    inbox: "Viestit",
    staff: "Tarkistettavat",
    platform: "Yritystiedot",
    tag: "AJANTASAISET AUKIOLOAJAT",
    title: "Oikeat ajat. Paremmat käynnit.",
    intro:
      "Luotettavasta tiedosta selkeäksi ehdotukseksi. Yrittäjä päättää muutoksesta.",
    mock: "SIMULOIDUT VIESTIT",
    sandbox: "SANDBOX · SIMULOIDUT VIESTIT",
    clock: "Demoaika",
    suggest: "Ehdotukset",
    flag: "Tarkistus tarvitaan",
    no_action: "Ei yhteydenottoa",
    runTitle: "Tarkastele yhtä yritystä · demo",
    search: "Etsi yritys",
    searchHint: "Hae nimellä tai tunnuksella…",
    business: "Yritys",
    date: "Kohdepäivä",
    run: "Havaitse ja ehdota",
    examples: "Kokeile esimerkkiä",
    history: "Pyhäpäivähistoria",
    closure: "Lopettamisepäily",
    correct: "Tiedot oikein",
    limited: "Ei historiaa",
    detect: "Havaitse",
    suggestStep: "Ehdota",
    contact: "Ota yhteyttä",
    decide: "Päätä",
    apply: "Tallenna ja vahvista",
    queue: "Tarkistusjono",
    all: "Kaikki",
    export: "Lataa CSV",
    businessCol: "Yritys / päivä",
    action: "Toiminto",
    reason: "Perustelu",
    priority: "Kiireellisyys",
    details: "Näytä tiedot",
    emptyTitle: "Hyvä päätös alkaa tiedosta.",
    emptyText:
      "Valitse yritys ja päivä. Tarkistamme perusteet ennen muutosehdotusta.",
    safety:
      "Alkuperäinen aineisto säilyy. Muutos tehdään vain valtuutetun päätöksen jälkeen. Julkaisuajat ovat malliaineiston arvioita.",
    connected: "Yhdistetty paikalliseen demoon",
    brandSub: "by OldJeans",
    sideTitle: "Oikeat aukioloajat kaikkialla.",
    sideText: "Tieto perustana. Yrittäjä päättää.",
    before: "Nykyiset ajat",
    after: "Ehdotetut ajat",
    confidence: "Perusteen vahvuus",
    evidence: "Miksi tämä ehdotus?",
    gaps: "Mitä tietoa puuttuu?",
    recheck: "Tarkistetaan uudelleen, kun",
    close: "Sulje",
    preview: "Esikatsele asiakasviesti",
    schedule: "Ajasta viesti",
    noOutreach: "Tästä tapauksesta ei lähetetä asiakasviestiä.",
    noHistory:
      "Odottaminen ei vahvista tietojen oikeellisuutta. Tarkistamme tilanteen, kun saamme lisätietoa.",
    resolve: "Kirjaa tarkistuksen tulos",
    resolution: "Tulos",
    note: "Muistiinpanot",
    noteHint: "Kerro havainnosta ja tarkistamistasi perusteista.",
    resolved: "Ratkaistu",
    needsOwner: "Kysy yrittäjältä",
    dismissed: "Suljettu",
    save: "Tallenna",
    saved: "Tallennettu",
    previewReady: "Viestin esikatselu on valmis viestikansiossa.",
    queued: "Viesti ajastettu",
    inboxTitle: "Selkeä keskustelu.",
    inboxIntro:
      "Esikatsele viestiä valitussa kanavassa ja avaa yrittäjän päätösnäkymä. Viestit ovat simuloituja.",
    emptyInbox: "Ei vielä viestejä",
    emptyInboxText:
      "Avaa ehdotus ja esikatsele viestiä aloittaaksesi yrittäjän päätöspolun.",
    openCustomer: "Avaa yrittäjän näkymä",
    channel: "Kanava",
    status: "Tila",
    scheduled: "Ajastettu",
    simulation:
      "Simuloitu lähetys · viestiä ei lähetetty oikealle asiakkaalle.",
    customerWelcome: "Sinä päätät aukioloajoista.",
    customerIntro:
      "Tarkista ehdotus. Voit hyväksyä sen, muokata sitä tai säilyttää nykyiset ajat.",
    approve: "Hyväksy ajat",
    reject: "Säilytä nykyiset",
    edit: "Muokkaa aikoja",
    editLabel: "Omat aukioloajat",
    editHint: "Kirjoita 07:30-15:00, useita aikavälejä tai closed.",
    confirmEdit: "Vahvista nämä ajat",
    cancel: "Peruuta",
    textLabel: "Tai kerro omin sanoin",
    textHint: "Esimerkiksi: avoinna 08:00-15:00",
    interpret: "Esikatsele vastaus",
    confirmReply: "Vahvista vastaus",
    previewOnly: "Tämä on esikatselu. Mitään ei muuteta ennen vahvistusta.",
    settings: "Yhteydenottoasetukset",
    frequency: "Kuinka usein otamme yhteyttä?",
    TWICE_MONTHLY: "Kahdesti kuussa · 1. ja 15.",
    MONTHLY: "Kerran kuussa · 1.",
    PAUSED: "Tauolla",
    optout: "Alkuperäisissä yhteystiedoissa on yhteydenottokielto.",
    nextContact: "Seuraava yhteydenotto",
    permissionTitle: "Lupa tuleviin pyhäpäiväkorjauksiin",
    permissionHelp:
      "Valinnainen: salli tarkistetut päiväkohtaiset korjaukset vain tälle pyhäpäivälle. Voit perua luvan milloin tahansa.",
    grant: "Salli tämä pyhäpäivä",
    revoke: "Peru lupa",
    permissionCheck:
      "Sallin tämän pyhäpäivän päiväkohtaiset korjaukset enintään vuodeksi.",
    result: "Päätöksesi",
    verified: "Ajat tallennettu ja tarkistettu.",
    rejected: "Nykyiset ajat säilytetty.",
    pending: "Päätös vastaanotettu.",
    failed: "Muutos vaatii tarkistusta.",
    resultExplain: "Tarkistimme tallennetut ajat lukemalla ne uudelleen.",
    estimate: "Missä muutos näkyy?",
    estimateNote:
      "Nämä ovat malliaineiston tyypillisiä päivitysaikoja, eivät vahvistus julkaisusta.",
    unknown: "Aika ei tiedossa",
    notStarted: "Päivitystä ei pyydetty.",
    refresh: "Päivitä tila",
    loading: "Ladataan…",
    busy: "Käsitellään…",
    error: "Pyyntöä ei voitu suorittaa.",
    noSession: "Avaa tämä sivu työtilan asiakasviestistä.",
    returnHome: "Takaisin työtilaan",
    expired: "Ehdotus on vanhentunut. Tarvitaan uusi tarkistus.",
    stale: "Ehdotus on muuttunut. Päivitä sivu ennen päätöstä.",
    unauthorized:
      "Istunnolla ei ole oikeutta tähän yritykseen tai ehdotukseen.",
    required: "Täytä pakolliset kentät.",
    dateInvalid: "Valitse demoaikaa myöhempi päivä.",
    limitedLabel: "Vähän tietoa",
    directLabel: "Suora tieto",
    partialLabel: "Osittainen tieto",
    URGENT: "Kiireellinen",
    HIGH: "Korkea",
    ROUTINE: "Tavallinen",
    MEDIUM: "Kohtalainen",
    SUGGEST: "Ehdota",
    FLAG: "Tarkistus",
    NO_ACTION: "Ei toimintoa",
    RETAIN: "Säilytä",
    DEFER: "Odota",
    STAFF_REVIEW: "Tarkistus",
    PROPOSAL_READY: "Ehdotus valmis",
    PENDING: "Odottaa",
    APPROVED: "Hyväksytty",
    EDITED: "Muokattu",
    REJECTED: "Hylätty",
    EXPIRED: "Vanhentunut",
    SUPERSEDED: "Korvattu",
    STANDING_AUTHORIZED: "Ennakkolupa",
    NOT_STARTED: "Ei aloitettu",
    SCHEDULED: "Ajastettu",
    SUCCEEDED: "Vahvistettu",
    FAILED: "Epäonnistui",
    CONFLICT: "Ristiriita",
    REVIEW_REQUIRED: "Tarkistus tarvitaan",
    DELIVERED_SIMULATED: "Toimitettu · simuloitu",
    QUEUED: "Jonossa",
    BLOCKED_OPT_OUT: "Yhteydenottokielto",
    BLOCKED_PAUSED: "Tauolla",
    closed: "Suljettu",
    dates: "Kohdepäivät",
    reviewSaved: "Tarkistus kirjattu",
    openEvidence: "Tietolähteet",
    permissionScope: "Luvan rajaus",
    permissionExpiry: "Voimassa asti",
    editPreview: "Tarkista lopullinen muutos",
    sourceLanguage: "Viesti on yrittäjän valitsemalla kielellä.",
    noProposal: "Ei aktiivista ehdotusta.",
    bundle: "Jokainen päivä hyväksytään erikseen. Muut päivät säilyvät.",
    emptyStaff: "Ei tarkistusta vaativia tapauksia.",
    clockNote: "Simuloitu aika · 6.11.2026",
    readiness: "Tarkistetaan yhteyttä…",
    retry: "Yritä uudelleen",
    runAll: "Toiminnallinen tarkistus",
    allScope:
      "Valitun yrityksen tarkistus seuraavaan yhteydenottoon + 2 päivää",
  },
};
const reasonTranslations = {
  ko: {
    HISTORY_PATTERN:
      "같은 공휴일에 업주가 설정했던 시간이 이번 제안의 근거입니다.",
    COMPARABLE_HOLIDAY: "비슷한 공휴일의 일관된 운영 이력을 확인했습니다.",
    CENTRE_ALIGNED: "쇼핑센터의 해당 날짜 시간과 과거 일치 기록이 근거입니다.",
    OWNER_CONFIRMED: "해당 날짜의 업주 확인 내용과 현재 표시 시간이 다릅니다.",
    FEEDBACK_REUSE: "업주가 이전에 확정한 시간을 근거로 다시 확인했습니다.",
    CURRENT_HOURS_SUPPORTED:
      "현재 표시 시간이 적용 가능한 최신 근거와 일치합니다.",
    INSUFFICIENT_EVIDENCE:
      "정확한 시간을 제안할 근거가 부족해 추가 정보를 기다립니다.",
    POSSIBLE_PERMANENT_CLOSURE:
      "서로 독립된 최근 근거가 폐업 가능성을 보여 직원 확인이 필요합니다.",
    AUTHORITATIVE_CONFLICT:
      "권위 있는 기록들이 충돌하며 최신 순서를 확인할 수 없습니다.",
    ALREADY_CLOSED:
      "이미 폐업으로 표시되어 있어 영업시간 연락을 하지 않습니다.",
    OWNER_REJECTED_UNCHANGED:
      "업주가 거절한 동일 제안입니다. 새로운 근거를 기다립니다.",
    DIRECT_SCHEDULE: "업주가 확인한 일정이 이 변경의 근거입니다.",
    OWN_CONTEXT_PATTERN:
      "비슷한 행사에서 업주가 설정한 시간이 운영 기회 제안의 근거입니다.",
  },
  fi: {
    HISTORY_PATTERN:
      "Yrittäjän aiemmin vahvistamat saman pyhäpäivän ajat tukevat ehdotusta.",
    COMPARABLE_HOLIDAY:
      "Samankaltaisten pyhäpäivien yhtenäinen oma historia tukee ehdotusta.",
    CENTRE_ALIGNED:
      "Kauppakeskuksen päiväkohtaiset ajat ja aiempi yhteneväisyys tukevat ehdotusta.",
    OWNER_CONFIRMED:
      "Yrittäjän päiväkohtainen vahvistus poikkeaa nykyisistä tiedoista.",
    FEEDBACK_REUSE:
      "Tarkistus perustuu yrittäjän aiemmin vahvistamiin aikoihin.",
    CURRENT_HOURS_SUPPORTED:
      "Nykyiset ajat vastaavat uusinta soveltuvaa tietoa.",
    INSUFFICIENT_EVIDENCE:
      "Tarkkojen aikojen ehdottamiseen ei ole riittävästi tietoa.",
    POSSIBLE_PERMANENT_CLOSURE:
      "Riippumattomat tuoreet havainnot viittaavat toiminnan päättymiseen.",
    AUTHORITATIVE_CONFLICT:
      "Luotettavat tiedot ovat ristiriidassa eikä niiden järjestys ole selvä.",
    ALREADY_CLOSED: "Yritys on jo merkitty suljetuksi; aikaviestiä ei tarvita.",
    OWNER_REJECTED_UNCHANGED:
      "Yrittäjä hylkäsi tämän muuttumattoman ehdotuksen. Odotamme uutta tietoa.",
    DIRECT_SCHEDULE: "Yrittäjän vahvistama aikataulu tukee tätä muutosta.",
    OWN_CONTEXT_PATTERN:
      "Omat aiemmat ajat vastaavissa tapahtumissa tukevat mahdollisuusehdotusta.",
  },
};
const reasonText = (x) =>
  (reasonTranslations[lang]?.[x.reason_code] || x.reason || x.summary || "").replaceAll("not_registered", t("notRegistered"));
const holidayNames = {
  XMAS_EVE: ["Christmas Eve", "크리스마스이브", "Jouluaatto"],
  XMAS_DAY: ["Christmas Day", "성탄절", "Joulupäivä"],
  BOXING_DAY: ["Boxing Day", "성탄절 다음 날", "Tapaninpäivä"],
  NYE: ["New Year’s Eve", "새해 전야", "Uudenvuodenaatto"],
  NEW_YEARS_DAY: ["New Year’s Day", "새해 첫날", "Uudenvuodenpäivä"],
  FATHERS_DAY: ["Father’s Day", "아버지의 날", "Isänpäivä"],
  INDEPENDENCE_DAY: ["Independence Day", "독립기념일", "Itsenäisyyspäivä"],
  EPIPHANY: ["Epiphany", "주현절", "Loppiainen"],
  EPIPHANY_EVE: ["Epiphany Eve", "주현절 전날", "Loppiaisaatto"],
  BLACK_FRIDAY: ["Black Friday", "블랙 프라이데이", "Black Friday"],
  DEC23: ["23 December", "12월 23일", "23. joulukuuta"],
  INTERDAY: ["Holiday period", "연말 중간일", "Välipäivä"],
  LUCIA: ["Saint Lucia’s Day", "성 루치아의 날", "Lucian päivä"],
  EVENT: ["Local event", "지역 행사", "Paikallinen tapahtuma"],
  SCHOOL_BREAK: ["School break", "학교 방학", "Koululoma"],
  REGULAR: ["Regular hours", "정규 영업시간", "Tavalliset aukioloajat"],
};
const holidayLabel = (k) =>
  holidayNames[k]?.[["en", "ko", "fi"].indexOf(lang)] || k.replaceAll("_", " ");
Object.assign(words.en, {
  bundlePreview: "Preview all ready dates",
  clarify:
    "Please confirm exact hours or choose the date. Nothing has changed.",
  unsupported: "Use the buttons or enter an exact time range.",
  invalidInput: "Check the requested date, hours and required fields.",
  scopeError: "The request exceeds the approved scope.",
  frequencyPreview: "Contact frequency",
  permissionPreview: "Allow corrections for this holiday only",
  editPreviewText: "Set the hours to",
  approvePreview: "Approve the proposed hours.",
  rejectPreview: "Keep the current hours.",
});
Object.assign(words.ko, {
  bundlePreview: "준비된 날짜를 묶어 미리보기",
  clarify:
    "정확한 시간 또는 대상 날짜를 확인해 주세요. 아직 변경하지 않았습니다.",
  unsupported: "버튼을 사용하거나 정확한 시간 범위를 입력해 주세요.",
  invalidInput: "날짜, 시간과 필수 입력값을 확인해 주세요.",
  scopeError: "승인된 변경 범위를 벗어나는 요청입니다.",
  frequencyPreview: "연락 주기",
  permissionPreview: "이 공휴일에 한해 수정 허용",
  editPreviewText: "다음 시간으로 변경",
  approvePreview: "제안한 영업시간을 승인합니다.",
  rejectPreview: "현재 영업시간을 유지합니다.",
});
Object.assign(words.fi, {
  bundlePreview: "Esikatsele kaikki valmiit päivät",
  clarify: "Vahvista tarkat ajat tai valitse päivä. Mitään ei ole muutettu.",
  unsupported: "Käytä painikkeita tai anna tarkka aikaväli.",
  invalidInput: "Tarkista päivä, ajat ja pakolliset tiedot.",
  scopeError: "Pyyntö ylittää hyväksytyn rajauksen.",
  frequencyPreview: "Yhteydenottotiheys",
  permissionPreview: "Salli korjaukset vain tälle pyhäpäivälle",
  editPreviewText: "Aseta ajoiksi",
  approvePreview: "Hyväksy ehdotetut ajat.",
  rejectPreview: "Säilytä nykyiset ajat.",
});
Object.assign(words.en, {
  replyUnavailable:
    "Reply assistance is unavailable. Your proposal is still waiting. Approve, keep your hours, or enter an exact time range using Edit hours.",
  replyWaiting: "Reading your reply… (up to 8 seconds)",
  replyPrivacy:
    "For natural-language help, your reply and proposed hours may be sent to Gemini. The buttons and exact time ranges work without reply assistance.",
  replyInput: "Write your reply",
  replyEngine: "Reply assistant",
  replyRetry: "Retry reply",
  replyTimeout:
    "The reply took too long. Nothing was changed. Please retry or use the buttons.",
  replyInvalid: "Please enter a reply (up to 2,000 characters).",
});
Object.assign(words.ko, {
  replyUnavailable:
    "답변 해석 서비스에 일시적인 문제가 있습니다. 변경하지 않았습니다. 다시 시도하거나 승인·수정·거절 버튼을 이용해 주세요.",
  replyWaiting: "답변을 해석하고 있습니다… (최대 8초)",
  replyPrivacy:
    "입력한 답변과 이 제안의 영업시간을 Gemini로 보내 해석합니다. 결과를 확인한 뒤 확정해 주세요.",
  replyInput: "답변 작성",
  replyEngine: "답변 도우미",
  replyRetry: "답변 다시 시도",
  replyTimeout:
    "답변 해석 시간이 초과되었습니다. 변경하지 않았습니다. 다시 시도하거나 버튼을 이용해 주세요.",
  replyInvalid: "답변을 2,000자 이내로 입력해 주세요.",
});
Object.assign(words.fi, {
  replyUnavailable:
    "Vastauksen tulkinta ei ole juuri nyt saatavilla. Mitään ei muutettu. Yritä uudelleen tai käytä toimintopainikkeita.",
  replyWaiting: "Tulkitaan vastausta… (enintään 8 sekuntia)",
  replyPrivacy:
    "Vastaus ja ehdotetut aukioloajat lähetetään Geminille tulkittavaksi. Tarkista tulos ennen vahvistamista.",
  replyInput: "Kirjoita vastaus",
  replyEngine: "Vastausavustaja",
  replyRetry: "Yritä uudelleen",
  replyTimeout:
    "Tulkinta kesti liian kauan. Mitään ei muutettu. Yritä uudelleen tai käytä painikkeita.",
  replyInvalid: "Kirjoita vastaus (enintään 2 000 merkkiä).",
});
Object.assign(words.en, {
  fleetTitle: "Start with every business",
  fleetIntro:
    "Check the complete dataset, prepare contact for actionable suggestions, then let each owner decide.",
  fleetScope: "Review scope",
  fleetOperational: "Operational: through next contact + 2 days",
  fleetDateMode: "Demo: one date for every business",
  fleetDate: "Demo target date",
  fleetScan: "Scan all businesses",
  fleetProcessed: "Businesses checked",
  fleetCases: "Business/date checks",
  fleetReady: "Businesses with pending suggestions",
  fleetContact: "Prepare scheduled contact",
  fleetPreview: "Create demo inbox now",
  fleetPreviewHint:
    "Demo preview bypasses dispatch timing; opt-out and pause still apply. No real messages are sent.",
  fleetContactHint:
    "Scheduled contact follows each owner’s cadence and preferred channel. FLAG goes to staff; NO_ACTION receives no outreach.",
  fleetDecideHint:
    "Open an owner view in Inbox: approve, reject or edit. Only a confirmed decision applies and verifies the change.",
  fleetCompanies: "companies",
  fleetStatus: "Run status",
  fleetFailures: "Failed business reads",
  fleetEmpty:
    "No full-dataset run yet. Single-business examples remain available below.",
  fleetOverlap:
    "A company can have different actions on different dates; company buckets can overlap.",
  fleetGoInbox: "Open Inbox",
  fleetAwaiting: "Awaiting owner decision",
  nextPage: "Next",
  previousPage: "Previous",
  pageRows: "Showing",
  RUNNING: "Running",
  COMPLETED: "Completed",
  COMPLETED_WITH_ERRORS: "Completed with gaps",
  INTERRUPTED: "Interrupted; run again",
  FAILED: "Failed",
  NOT_PREPARED: "Not prepared",
});
Object.assign(words.ko, {
  fleetTitle: "모든 업체에서 시작하기",
  fleetIntro:
    "전체 데이터에서 변경이 필요한 업체를 찾고 연락을 준비합니다. 최종 결정은 각 업주가 내립니다.",
  fleetScope: "검사 범위",
  fleetOperational: "실제 운영: 다음 연락일 + 2일까지",
  fleetDateMode: "데모: 모든 업체의 특정일 검사",
  fleetDate: "데모 대상일",
  fleetScan: "전체 업체 검사",
  fleetProcessed: "검사한 업체",
  fleetCases: "업체·날짜 검사 건수",
  fleetReady: "결정을 기다리는 제안이 있는 업체",
  fleetContact: "연락 일정 준비",
  fleetPreview: "데모 받은편지함 즉시 만들기",
  fleetPreviewHint:
    "데모 미리보기는 발송 시점만 앞당깁니다. 수신 거부·연락 정지는 지키며 실제 메시지는 보내지 않습니다.",
  fleetContactHint:
    "예약 연락은 업주의 주기와 선호 채널을 따릅니다. FLAG는 직원 확인, NO_ACTION은 연락 없이 유지합니다.",
  fleetDecideHint:
    "받은편지함에서 업주 화면을 열어 승인·거절·수정을 선택합니다. 확정한 결정만 반영하고 재조회합니다.",
  fleetCompanies: "개 업체",
  fleetStatus: "전체 실행 상태",
  fleetFailures: "정보 조회 실패 업체",
  fleetEmpty:
    "아직 전체 검사를 실행하지 않았습니다. 아래에서는 개별 사례도 확인할 수 있습니다.",
  fleetOverlap: "날짜별 액션이 달라 한 업체가 여러 분류에 포함될 수 있습니다.",
  fleetGoInbox: "받은편지함 열기",
  fleetAwaiting: "업주 결정 대기",
  nextPage: "다음",
  previousPage: "이전",
  pageRows: "표시 범위",
  RUNNING: "진행 중",
  COMPLETED: "완료",
  COMPLETED_WITH_ERRORS: "일부 누락 상태로 완료",
  INTERRUPTED: "중단됨 · 다시 실행 필요",
  FAILED: "실패",
  NOT_PREPARED: "준비 전",
});
Object.assign(words.fi, {
  fleetTitle: "Aloita kaikista yrityksistä",
  fleetIntro:
    "Tarkista koko aineisto, valmistele yhteydenotot ja anna yrittäjän päättää.",
  fleetScope: "Tarkastuksen laajuus",
  fleetOperational: "Toiminta: seuraava yhteydenotto + 2 päivää",
  fleetDateMode: "Demo: yksi päivä kaikille yrityksille",
  fleetDate: "Demon kohdepäivä",
  fleetScan: "Tarkista kaikki yritykset",
  fleetProcessed: "Tarkistetut yritykset",
  fleetCases: "Yritys- ja päivätarkistukset",
  fleetReady: "Yritykset, joilla on odottava ehdotus",
  fleetContact: "Valmistele ajoitetut viestit",
  fleetPreview: "Luo demon viestit heti",
  fleetPreviewHint:
    "Demo ohittaa lähetysajan, mutta noudattaa viestikieltoa ja taukoa. Oikeita viestejä ei lähetetä.",
  fleetContactHint:
    "Ajoitus noudattaa yrittäjän asetuksia. FLAG menee henkilökunnalle; NO_ACTION ei lähetä viestiä.",
  fleetDecideHint:
    "Avaa yrittäjän näkymä viesteistä: hyväksy, hylkää tai muokkaa. Vain vahvistettu päätös tallennetaan ja tarkistetaan.",
  fleetCompanies: "yritystä",
  fleetStatus: "Tarkistuksen tila",
  fleetFailures: "Epäonnistuneet yrityshaut",
  fleetEmpty:
    "Koko aineistoa ei ole vielä tarkistettu. Yksittäiset esimerkit ovat alla.",
  fleetOverlap:
    "Yrityksellä voi olla eri toiminto eri päivinä; yritysmäärät voivat mennä päällekkäin.",
  fleetGoInbox: "Avaa viestit",
  fleetAwaiting: "Odottaa yrittäjän päätöstä",
  nextPage: "Seuraava",
  previousPage: "Edellinen",
  pageRows: "Näytetään",
  RUNNING: "Käynnissä",
  COMPLETED: "Valmis",
  COMPLETED_WITH_ERRORS: "Valmis, puutteita",
  INTERRUPTED: "Keskeytynyt",
  FAILED: "Epäonnistui",
  NOT_PREPARED: "Ei valmisteltu",
});
function draftText(d) {
  if (d.status === "UNAVAILABLE")
    return t(
      d.interpretation?.error_code === "TIMEOUT"
        ? "replyTimeout"
        : "replyUnavailable",
    );
  if (d.status === "NEEDS_CLARIFICATION") return t("clarify");
  if (d.status === "UNSUPPORTED") return t("unsupported");
  if (d.intent === "EDIT")
    return (
      t("editPreviewText") + " " + changeText(d.decision_draft.edited_change)
    );
  if (d.intent === "APPROVE") return t("approvePreview");
  if (d.intent === "REJECT") return t("rejectPreview");
  if (d.preference_draft)
    return t("frequencyPreview") + ": " + t(d.preference_draft.frequency);
  if (d.permission_draft)
    return (
      t("permissionPreview") +
      ": " +
      d.permission_draft.day_keys.map(holidayLabel).join(", ")
    );
  return d.preview;
}
const lang = "en";
try { localStorage.setItem("connect-language", "en"); } catch {}
const t = (k) => words[lang][k] ?? words.en[k] ?? k;
const h = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const app = document.querySelector("#app"),
  dialog = document.querySelector("#detail");

const SANDBOX_TEXT = {
 en: {openSandbox:"Test real Yext apply",backToMock:"All businesses · mock",sandboxTitle:"Team sandbox · real apply",sandboxIntro:"Preview the message, open the owner view, then approve. Approval writes only the displayed date to the team Yext sandbox.",sandboxEvidence:"Demo evidence source",realTarget:"Actual Yext target",sandboxDemo:"Create test suggestion & message",sandboxRead:"Read current Yext hours",sandboxNoChange:"No new suggestion for this date. Inspect the result or choose another date.",notRegistered:"Not registered",recipient:"Demo recipient",deliveryDemo:"Simulated delivery · no external message sent",liveVerified:"Saved to Yext sandbox and independently read back",currentYext:"Current hours read from Yext",notTested:"No verified write yet",writeVerified:"Write verified",writeFailed:"Write failed"},
 ko: {openSandbox:"실제 Yext 적용 테스트",backToMock:"전체 업체 · 모의 환경",sandboxTitle:"팀 샌드박스 · 실제 적용",sandboxIntro:"모의 메시지를 확인하고 업주 화면에서 승인하세요. 승인하면 표시된 날짜만 팀 Yext 샌드박스에 저장됩니다.",sandboxEvidence:"데모 근거의 출처",realTarget:"실제 Yext 적용 대상",sandboxDemo:"테스트 제안·모의 메시지 만들기",sandboxRead:"현재 Yext 영업시간 조회",sandboxNoChange:"이 날짜의 새 제안이 없습니다. 결과를 확인하거나 다른 날짜를 선택하세요.",notRegistered:"미등록",recipient:"모의 수신자",deliveryDemo:"모의 발송 · 외부 메시지는 전송되지 않음",liveVerified:"Yext 샌드박스 저장 후 재조회 확인 완료",currentYext:"Yext에서 조회한 현재 영업시간",notTested:"확인된 쓰기 기록 없음",writeVerified:"쓰기 검증 완료",writeFailed:"쓰기 실패"},
 fi: {openSandbox:"Testaa Yext-tallennusta",backToMock:"Kaikki yritykset · simulaatio",sandboxTitle:"Tiimin testiympäristö · oikea tallennus",sandboxIntro:"Esikatsele viesti, avaa omistajan näkymä ja hyväksy. Hyväksyntä tallentaa vain valitun päivän tiimin Yext-testiympäristöön.",sandboxEvidence:"Demon tietolähde",realTarget:"Todellinen Yext-kohde",sandboxDemo:"Luo ehdotus ja testiviesti",sandboxRead:"Hae nykyiset Yext-aukioloajat",sandboxNoChange:"Ei uutta ehdotusta tälle päivälle. Tarkista tulos tai valitse toinen päivä.",notRegistered:"Ei ilmoitettu",recipient:"Demon vastaanottaja",deliveryDemo:"Simuloitu lähetys · ei ulkoista viestiä",liveVerified:"Tallennettu Yextiin ja tarkistettu uudella haulla",currentYext:"Yextistä haetut nykyiset aukioloajat",notTested:"Tallennusta ei ole vielä vahvistettu",writeVerified:"Tallennus vahvistettu",writeFailed:"Tallennus epäonnistui"}
};
for (const [locale, values] of Object.entries(SANDBOX_TEXT)) Object.assign(words[locale], values);

const RESET_TEXT = {
  "en": {
    "reset": "Reset demo",
    "resetTitle": "Return to the original data",
    "resetMock": "Restore all mock businesses to the received dataset. Clear this workspace’s suggestions, messages, decisions, schedules and preferences.",
    "resetSandbox": "Restore this team Yext entity’s hours to the verified state before the first Apply. Clear only this sandbox workspace’s progress.",
    "resetBackup": "A private backup is saved first. Old owner links stop working. Original dataset files and API keys are kept.",
    "resetConfirm": "Back up and reset",
    "resetCounts": "Current records",
    "resetCases": "Cases",
    "resetMessages": "Messages",
    "resetDecisions": "Decisions",
    "resetSuccess": "Reset complete. You can run the demo again.",
    "resetLoading": "Checking the original data and current changes…",
    "resetRecover": "An earlier reset needs recovery. Retry from the saved backup.",
    "EXTERNAL_CHANGES": "Yext contains changes outside this app’s verified writes. Reset is blocked to preserve them.",
    "RESET_PREVIEW_STALE": "Data changed while the dialog was open. Reopen Reset to review it again.",
    "RESET_RECOVERY_REQUIRED": "Reset could not finish. Progress is backed up; reopen Reset to retry.",
    "BASELINE_CHANGED": "The original dataset changed. Reset is blocked.",
    "BASELINE_UNAVAILABLE": "No verified original state exists for this target.",
    "RUN_ACTIVE": "Wait for the running scan/contact job to finish.",
    "RESET_TARGET_CHANGED": "The reset target changed. Recovery needs review.",
    "resetOriginalHours": "Original hours to restore"
  },
  "ko": {
    "reset": "데모 초기화",
    "resetTitle": "원본 데이터로 초기화",
    "resetMock": "모든 모의 업체를 제공받은 원본 데이터로 복원합니다. 이 환경의 제안·메시지·결정·예약·연락 설정을 비웁니다.",
    "resetSandbox": "이 팀 Yext 업체의 영업시간을 최초 적용 전 확인된 값으로 복원합니다. 이 샌드박스 환경의 진행 기록만 비웁니다.",
    "resetBackup": "먼저 현재 상태를 백업합니다. 이전 업주 링크는 만료됩니다. 원본 파일과 API 키는 유지됩니다.",
    "resetConfirm": "백업 후 초기화",
    "resetCounts": "현재 진행 기록",
    "resetCases": "검사",
    "resetMessages": "메시지",
    "resetDecisions": "결정",
    "resetSuccess": "초기화했습니다. 다시 처음부터 테스트할 수 있습니다.",
    "resetLoading": "원본과 현재 변경 내용을 확인하고 있습니다…",
    "resetRecover": "이전 초기화를 마쳐야 합니다. 저장된 백업을 기준으로 다시 시도합니다.",
    "EXTERNAL_CHANGES": "우리 앱이 적용한 기록과 다른 Yext 변경이 있어 초기화를 중단했습니다. 해당 변경을 먼저 확인하세요.",
    "RESET_PREVIEW_STALE": "창을 연 뒤 데이터가 바뀌었습니다. 초기화 창을 다시 열어 확인하세요.",
    "RESET_RECOVERY_REQUIRED": "초기화를 마치지 못했습니다. 진행 내용은 백업되어 있습니다. 초기화 창을 다시 열어 재시도하세요.",
    "BASELINE_CHANGED": "처음 받은 원본 파일이 바뀌어 초기화를 중단했습니다.",
    "BASELINE_UNAVAILABLE": "이 대상의 최초 상태를 확인할 수 없어 초기화할 수 없습니다.",
    "RUN_ACTIVE": "검사 또는 연락 준비가 끝난 뒤 초기화하세요.",
    "RESET_TARGET_CHANGED": "초기화 대상이 달라졌습니다. 복원 대상을 확인해야 합니다.",
    "resetOriginalHours": "복원할 초기 영업시간"
  },
  "fi": {
    "reset": "Nollaa demo",
    "resetTitle": "Palauta alkuperäiset tiedot",
    "resetMock": "Palauta kaikki simuloidut yritykset alkuperäiseen aineistoon. Tyhjennä tämän työtilan ehdotukset, viestit, päätökset, ajastukset ja asetukset.",
    "resetSandbox": "Palauta tiimin Yext-yrityksen aukioloajat ensimmäistä muutosta edeltäneeseen vahvistettuun tilaan. Tyhjennä vain tämän testiympäristön edistyminen.",
    "resetBackup": "Nykytila varmuuskopioidaan ensin. Vanhat omistajalinkit lakkaavat toimimasta. Alkuperäinen aineisto ja API-avaimet säilyvät.",
    "resetConfirm": "Varmuuskopioi ja nollaa",
    "resetCounts": "Nykyiset tiedot",
    "resetCases": "Tapaukset",
    "resetMessages": "Viestit",
    "resetDecisions": "Päätökset",
    "resetSuccess": "Nollaus valmis. Voit testata demon uudelleen.",
    "resetLoading": "Tarkistetaan alkuperäisiä tietoja ja muutoksia…",
    "resetRecover": "Aiempi nollaus jäi kesken. Jatka varmuuskopiosta.",
    "EXTERNAL_CHANGES": "Yextissä on sovelluksen ulkopuolisia muutoksia. Nollaus on estetty niiden säilyttämiseksi.",
    "RESET_PREVIEW_STALE": "Tiedot muuttuivat. Avaa nollausikkuna uudelleen.",
    "RESET_RECOVERY_REQUIRED": "Nollaus jäi kesken. Varmuuskopio on tallennettu; avaa nollaus uudelleen.",
    "BASELINE_CHANGED": "Alkuperäinen aineisto on muuttunut. Nollaus estetty.",
    "BASELINE_UNAVAILABLE": "Kohteen alkuperäistä tilaa ei ole vahvistettu.",
    "RUN_ACTIVE": "Odota käynnissä olevan työn valmistumista.",
    "RESET_TARGET_CHANGED": "Nollauksen kohde muuttui. Tarkista palautus.",
    "resetOriginalHours": "Palautettavat alkuperäiset aukioloajat"
  }
};
for (const [locale, values] of Object.entries(RESET_TEXT)) Object.assign(words[locale], values);
let state = {
  tab: APP_BASE || new URLSearchParams(location.search).get("view") === "workspace" ? "overview" : "demo",
  demo: newDemoState(),
  fleet: null,
  fleetTotal: null,
  fleetScope: "OPERATIONAL",
  fleetDate: "2026-12-24",
  caseOffset: 0,
  messageOffset: 0,
  messageMode: "ALL",
  messageTotal: 0,
  filter: "ALL",
  cases: [],
  businesses: [],
  messages: [],
  health: null,
  selected: "FI-D0001",
  date: "2026-12-24",
  owner: null,
  proposals: [],
  preferences: null,
  permissions: [],
  drafts: {},
  replyText: {},
  replyBusy: {},
  editing: null,
};
function cookie(n) {
  return (
    document.cookie
      .split("; ")
      .find((x) => x.startsWith(n + "="))
      ?.slice(n.length + 1) || ""
  );
}
function toast(s) {
  let el = document.querySelector("#toast");
  el.textContent = s;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 4500);
}
function errorText(e) {
  if (RESET_TEXT.en[e.code]) return t(e.code);
  return e.status === 410
    ? t("expired")
    : e.status === 409
      ? t("stale")
      : [401, 403].includes(e.status)
        ? t("unauthorized")
        : e.status === 422
          ? t("invalidInput")
          : e.status >= 500
            ? t("error")
            : e.message || t("error");
}
async function api(path, method = "GET", body, idem, signal) {
  const headers = { Accept: "application/json" };
  if (!IS_OWNER)
    headers["X-Operator-View"] = "1";
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET")
    headers["X-CSRF-Token"] = decodeURIComponent(cookie(APP_BASE ? "sandbox_csrf_token" : "csrf_token"));
  if (idem) headers["Idempotency-Key"] = idem;
  const response = await fetch(APP_BASE + path, {
    method,
    signal,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (path === "/api/v1/health")
    state.clock = response.headers.get("X-App-Time");
  if (!response.ok) {
    let j;
    try {
      j = await response.json();
    } catch {
      j = {};
    }
    let e = new Error(j.error?.message || t("error"));
    e.status = response.status;
    e.code = j.error?.code;
    throw e;
  }
  if (response.status === 204) return {};
  return response.headers.get("Content-Type")?.includes("json")
    ? response.json()
    : response.text();
}
const key = () => crypto.randomUUID();
const dateLabel = (v, tz) => {
  try {
    return new Intl.DateTimeFormat(
      lang === "ko" ? "ko-KR" : lang === "fi" ? "fi-FI" : "en-GB",
      {
        day: "numeric",
        month: "short",
        year: "numeric",
        ...(v.length > 10
          ? { hour: "2-digit", minute: "2-digit", hour12: false }
          : {}),
        timeZone: tz || "Europe/Helsinki",
      },
    ).format(new Date(v.length === 10 ? v + "T12:00:00Z" : v));
  } catch {
    return v;
  }
};
const hours = (v) => (v === "closed" ? t("closed") : v === "not_registered" ? t("notRegistered") : v);
const changeText = (c) =>
  !c
    ? "—"
    : c.kind === "DATE_HOURS"
      ? hours(c.hours)
      : c.kind === "REOPEN_DATE"
        ? dateLabel(c.reopen_date)
        : Object.entries(c.weekdays)
            .map(([d, v]) => d + ": " + hours(v))
            .join(" · ");
function language() {
  return `<span class="language-label">English demo</span>`;
}
function brand() {
  return `<div class="brand"><span class="brand-mark">c<span class="sr-only">onnect</span></span><span>Connect Suggests<br><small>${t("brandSub")}</small></span></div>`;
}
function badge(v) {
  return `<span class="badge ${h(v.toLowerCase())}">${h(t(v))}</span>`;
}
function evidence(items = []) {
  return items
    .map(
      (e) =>
        `<div class="evidence"><small>${h(e.role)} · ${h(dateLabel(e.known_at))}</small><p>${h(e.summary)}</p><code>${h(e.source_file)} · ${h(e.source_record)}</code></div>`,
    )
    .join("");
}
function scheduleView(p) {
  return `<div class="schedule"><div><small>${t("before")}</small><strong>${h(changeText(p.baseline))}</strong></div><span class="arrow">→</span><div><small>${t("after")}</small><strong>${h(changeText(p.change))}</strong></div></div>`;
}
function businessName(id) {
  return state.businesses.find((b) => b.entity_id === id)?.business_name || id;
}
function empty(title, desc) {
  return `<div class="empty"><div class="empty-icon">⌁</div><h3>${h(title)}</h3><p>${h(desc)}</p></div>`;
}
function render() {
  document.documentElement.lang = lang;
  document.title = "Connect Suggests";
  if (IS_OWNER) return renderCustomer();
  renderOperator();
}
function renderOperator() {
  const counts = Object.fromEntries(
    ["SUGGEST", "FLAG", "NO_ACTION"].map((a) => [
      a,
      state.cases.filter((c) => c.action === a).length,
    ]),
  );
  app.innerHTML = `<div class="shell"><aside class="sidebar">${brand()}<div class="label">${t("workspace")}</div><nav class="nav">${[
    ["demo", "◉"],
    ["overview", "▦"],
    ["inbox", "✉"],
    ["staff", "⚑"],
  ]
    .filter(([tab]) => !APP_BASE || tab !== "demo")
    .map(
      ([tab, icon]) =>
        `<button data-tab="${tab}" class="${state.tab === tab ? "active" : ""}"><span>${icon}</span>${t(tab)}</button>`,
    )
    .join(
      "",
    )}</nav><div class="sidebar-bottom"><strong>${t("sideTitle")}</strong>${t("sideText")}<br><br>Fonecta × SinceAI 2026</div></aside><main class="main"><header class="topbar"><div class="breadcrumb">Connect / ${t("platform")}</div><div class="top-actions"><span class="badge mock">● ${t(state.health?.mode === "sandbox" ? "sandbox" : "mock")}</span>${APP_BASE || state.health?.sandbox_available ? `<a class="workspace-switch" href="${APP_BASE ? "/" : "/sandbox/"}">${t(APP_BASE ? "backToMock" : "openSandbox")}</a>` : ""}<button class="small reset-control" id="reset-open">↺ ${t("reset")}</button>${language()}</div></header><div class="hero"><div><p class="eyebrow">${t("tag")}</p><h1>${state.tab === "demo" ? "From a signal to the right hours." : state.tab === "inbox" ? t("inboxTitle") : t("title")}</h1><p>${state.tab === "demo" ? "Follow the complete journey: check the evidence, offer a change, reach the owner and verify the outcome." : state.tab === "inbox" ? t("inboxIntro") : t("intro")}</p></div><div class="hero-icon" aria-hidden="true"><svg viewBox="0 0 48 48"><rect x="8" y="10" width="32" height="30" rx="6"/><path d="M8 20h32M16 6v8M32 6v8m-15 15 5 5 10-11"/></svg></div></div>${
    state.tab === "demo"
      ? renderDemo()
      : state.tab === "inbox"
      ? renderInbox()
      : `<section class="stats">${[
          ["SUGGEST", "suggest", "↗"],
          ["FLAG", "flag", "⚑"],
          ["NO_ACTION", "no_action", "✓"],
        ]
          .map(
            ([a, l, i]) =>
              `<div class="stat"><div><div class="stat-value">${counts[a]}</div><div class="stat-label">${t(l)}</div></div><div class="stat-icon">${i}</div></div>`,
          )
          .join(
            "",
          )}</section>${renderFleet()}${renderControls()}<section class="panel"><div class="panel-head"><h2>${state.tab === "staff" ? t("staff") : t("queue")}</h2><div class="filters">${["ALL", "SUGGEST", "FLAG", "NO_ACTION"].map((a) => `<button data-filter="${a}" class="${state.filter === a ? "active" : ""}">${a === "ALL" ? t("all") : t(a)}</button>`).join("")}</div><button class="small" id="export">↓ ${t("export")}</button></div>${renderCases()}</section>`
  }<div class="footer-note">${t("safety")}</div><div class="footer-note">${state.health ? t("connected") : t("readiness")} · ${state.health?.clock_mode === "REAL" ? "Live clock" : t("clock") + " · " + (state.clock ? dateLabel(state.clock) : "—")}</div></main></div>`;
  bindCommon();
}
function pager(kind, offset, total) {
  if (total <= 50) return "";
  return `<div class="pagination"><small>${t("pageRows")} ${offset + 1}–${Math.min(offset + 50, total)} / ${total}</small><button class="small" data-page-kind="${kind}" data-offset="${Math.max(0, offset - 50)}" ${offset === 0 ? "disabled" : ""}>${t("previousPage")}</button><button class="small" data-page-kind="${kind}" data-offset="${offset + 50}" ${offset + 50 >= total ? "disabled" : ""}>${t("nextPage")}</button></div>`;
}
async function refreshMessages() {
  const result = await api(
    `/api/v1/operator/messages?offset=${state.messageOffset}&limit=50${state.messageMode === "ALL" ? "" : "&delivery_mode=" + state.messageMode}`,
  );
  state.messages = result.items;
  state.messageTotal = result.total ?? result.items.length;
}

function renderSandbox() {
 const s = state.sandbox;
 if (!s) return `<section class="panel">${t("sandboxTitle")}</section>`;
 const rows = Object.entries(s.hours).filter(([k]) => k !== "holidayHours").map(([k,v]) => `<li><strong>${h(k)}</strong> ${h(typeof v === "object" ? JSON.stringify(v) : v)}</li>`).join("");
 const holidays = (s.hours.holidayHours || []).map(d => `<li><strong>${h(dateLabel(d.date))}</strong> ${h(d.isClosed ? t("closed") : d.isRegularHours ? "Regular hours" : (d.openIntervals || []).map(i => i.start + "–" + i.end).join(", "))}</li>`).join("");
 return `<section class="panel sandbox-panel" id="sandbox-panel"><div class="panel-head"><h2>${t("sandboxTitle")}</h2><span class="badge ${s.write_status === "VERIFIED" ? "succeeded" : "mock"}">${t(s.write_status === "VERIFIED" ? "writeVerified" : s.write_status === "FAILED" ? "writeFailed" : "notTested")}</span></div><p>${t("sandboxIntro")}</p><div class="notice"><strong>${t("realTarget")}: ${h(s.target_name)} · ${h(s.target_entity_id)}</strong><br>${t("sandboxEvidence")}: ${h(businessName(s.source_entity_id))} · ${h(s.source_entity_id)}</div><div class="actions"><button class="primary" id="sandbox-demo">${t("sandboxDemo")}</button><button id="sandbox-refresh">${t("sandboxRead")}</button></div><h3>${t("currentYext")}</h3><ul class="sandbox-hours">${rows || holidays ? rows + holidays : `<li>${t("notRegistered")}</li>`}</ul><small>${h(dateLabel(s.checked_at))}</small></section>`;
}

function renderFleet() {
  if (APP_BASE) return renderSandbox();
  const j = state.fleet,
    busy = j && (j.status === "RUNNING" || j.contact_status === "RUNNING");
  const complete =
    j && ["COMPLETED", "COMPLETED_WITH_ERRORS"].includes(j.status);
  const pct = j?.total_businesses
    ? Math.round((j.processed_businesses / j.total_businesses) * 100)
    : 0;
  return `<section class="panel fleet-panel" id="fleet-panel"><div class="panel-head"><div><p class="eyebrow">DETECT → SUGGEST → CONTACT → DECIDE → APPLY</p><h2>${t("fleetTitle")}</h2></div><span class="badge mock">${state.fleetTotal ?? "—"} ${t("fleetCompanies")}</span></div><p class="muted">${t("fleetIntro")}</p><div class="fleet-controls"><label>${t("fleetScope")}<select id="fleet-scope" ${busy ? "disabled" : ""}><option value="OPERATIONAL" ${state.fleetScope === "OPERATIONAL" ? "selected" : ""}>${t("fleetOperational")}</option><option value="EXPLICIT_DATE" ${state.fleetScope === "EXPLICIT_DATE" ? "selected" : ""}>${t("fleetDateMode")}</option></select></label>${state.fleetScope === "EXPLICIT_DATE" ? `<label>${t("fleetDate")}<input type="date" id="fleet-date" value="${h(state.fleetDate)}" ${busy ? "disabled" : ""}></label>` : ""}<button class="primary" id="fleet-start" ${busy || state.health?.mode === "sandbox" ? "disabled" : ""}>${busy ? `<span class="spinner"></span>` : ""}${t("fleetScan")}</button></div>${
    j
      ? `<div class="fleet-progress" aria-live="polite"><p data-fleet-result-scope><small>${t("fleetScope")}: ${j.scope === "EXPLICIT_DATE" ? t("fleetDateMode") + " · " + h(dateLabel(j.date)) : t("fleetOperational")}</small></p><div class="meta-row"><strong>${t("fleetProcessed")}: ${j.processed_businesses} / ${j.total_businesses}</strong><span>${h(t(j.status))} · ${j.elapsed_seconds}s</span></div><progress max="100" value="${pct}" aria-label="${t("fleetProcessed")}"></progress><div class="fleet-counts">${["SUGGEST", "FLAG", "NO_ACTION"].map((k) => `<div>${badge(k)}<strong>${j.counts[k]}</strong><small>${j.business_counts[k]} ${t("fleetCompanies")}</small></div>`).join("")}</div><small>${t("fleetCases")}: ${j.case_count} · ${t("fleetFailures")}: ${j.failed_businesses}<br>${t("fleetOverlap")}</small>${j.error_code ? `<div class="notice warn">${h(j.error_code)}</div>` : ""}</div><div class="fleet-contact"><h3>3 · ${t("contact")}</h3><p>${t("fleetReady")}: <strong>${j.ready_businesses}</strong></p><p class="muted">${t("fleetContactHint")}</p><div class="actions"><button data-fleet-contact="SCHEDULED" ${!complete || busy || !j.ready_businesses ? "disabled" : ""}>${t("fleetContact")}</button><button data-fleet-contact="PREVIEW" ${!complete || busy || !j.ready_businesses ? "disabled" : ""}>${t("fleetPreview")}</button></div><small>${t("fleetPreviewHint")}</small><p data-contact-status>${t(j.contact_status)} · ${j.contact_processed} ${t("fleetCompanies")}</p><div class="meta-row">${Object.entries(
          j.contact_counts,
        )
          .map(([k, v]) => `<span>${h(t(k))}: <b>${v}</b></span>`)
          .join(
            "",
          )}</div></div><div class="fleet-owner"><h3>4–5 · ${t("decide")} → ${t("apply")}</h3><p class="muted">${t("fleetDecideHint")}</p><button class="small" data-tab="inbox">${t("fleetGoInbox")} →</button></div>`
      : `<p class="muted">${t("fleetEmpty")}</p>`
  }</section>`;
}
let fleetPoll;
function scheduleFleetPoll() {
  clearTimeout(fleetPoll);
  fleetPoll = setTimeout(async () => {
    try {
      await refreshFleet();
    } catch (e) {
      toast(errorText(e));
      scheduleFleetPoll();
    }
  }, 1200);
}
async function refreshFleet() {
  const old = state.fleet;
  if (APP_BASE) {state.sandbox = await api("/api/v1/operator/sandbox-state"); state.selected = state.sandbox.source_entity_id; return;}
  const data = await api("/api/v1/operator/fleet-runs");
  state.fleet = data.run;
  state.fleetTotal = data.total_businesses;
  if (!old && data.run) {state.fleetScope = data.run.scope; if (data.run.date) state.fleetDate = data.run.date;}
  const busy =
    data.run &&
    (data.run.status === "RUNNING" || data.run.contact_status === "RUNNING");
  if (busy) scheduleFleetPoll();
  if (
    old &&
    (old.status === "RUNNING" || old.contact_status === "RUNNING") &&
    !busy
  ) {
    await refreshCases();
    if (state.tab === "inbox") await refreshMessages();
    state.caseOffset = 0;
    render();
  } else {
    const panel = document.getElementById("fleet-panel");
    if (panel) panel.outerHTML = renderFleet();
  }
}
app.addEventListener("change", async (e) => {
  if (e.target.id === "demo-date") {
    Object.assign(state.demo, {date: e.target.value, stage: 1, run: null, runId: null, proposal: null, proposalId: null, message: null, messageId: null, result: null});
    saveDemo(); render();
  }
  if (e.target.id === "message-mode") {
    state.messageMode = e.target.value;
    state.messageOffset = 0;
    try {
      await refreshMessages();
      render();
    } catch (error) {
      toast(errorText(error));
    }
  }
  if (e.target.id === "fleet-scope") {
    state.fleetScope = e.target.value;
    document.getElementById("fleet-panel").outerHTML = renderFleet();
  }
  if (e.target.id === "fleet-date") state.fleetDate = e.target.value;
});

function renderControls() {
  return `<section class="panel"><div class="workflow">${["detect", "suggestStep", "contact", "decide", "apply"].map((s, i) => `<span><i>${i + 1}</i>${t(s)}</span>${i < 4 ? "<b>→</b>" : ""}`).join("")}</div><div class="panel-head"><h2>${t("runTitle")}</h2></div><div class="controls"><label>${t("search")}<input id="search" placeholder="${t("searchHint")}" autocomplete="off"></label><label>${t("business")}<select id="business">${businessOptions()}</select></label><label>${t("date")}<input type="date" id="target-date" value="${h(state.date)}"></label><button id="run" class="primary">${t("run")} ↗</button></div><div class="examples"><small>${t("examples")}</small>${[
    ["FI-D0001", "history"],
    ["FI-D0011", "closure"],
    ["FI-D0013", "correct"],
    ["FI-D0017", "limited"],
  ]
    .filter(([id]) => !APP_BASE || id === state.selected)
    .map(
      ([id, l]) => `<button class="pill" data-example="${id}">${t(l)}</button>`,
    )
    .join(
      "",
    )}<button class="pill" id="operational" title="${t("allScope")}">${t("runAll")}</button></div></section>`;
}
function businessOptions() {
  const selected = state.businesses.find((b) => b.entity_id === state.selected);
  return `${!selected ? `<option value="${h(state.selected)}">${h(state.selected)}</option>` : ""}${state.businesses.map((b) => `<option value="${h(b.entity_id)}" ${b.entity_id === state.selected ? "selected" : ""}>${h(b.business_name)} · ${h(b.entity_id)}</option>`).join("")}`;
}
function renderCases() {
  const cases = state.cases.filter(
    (c) =>
      (state.tab !== "staff" || c.action === "FLAG") &&
      (state.filter === "ALL" || c.action === state.filter),
  );
  if (!cases.length)
    return empty(
      state.tab === "staff" ? t("emptyStaff") : t("emptyTitle"),
      t("emptyText"),
    );
  return `<div class="table-wrap"><table class="table"><thead><tr><th>${t("businessCol")}</th><th>${t("action")}</th><th>${t("reason")}</th><th>${t("priority")}</th><th><span class="sr-only">${t("details")}</span></th></tr></thead><tbody>${cases
    .slice(state.caseOffset, state.caseOffset + 50)
    .map(
      (c) =>
        `<tr><td><span class="name">${h(c.business_name || businessName(c.entity_id))}</span><small class="date">${h(dateLabel(c.target_date))} · ${h(c.entity_id)}</small></td><td>${badge(c.action)}<br><small>${h(t(c.status))}</small></td><td><span class="reason">${h(reasonText(c))}</span></td><td>${badge(c.priority)}</td><td><button class="small" data-case="${h(c.case_id)}">${t("details")} →</button></td></tr>`,
    )
    .join(
      "",
    )}</tbody></table></div>${pager("cases", state.caseOffset, cases.length)}`;
}
function renderInbox() {
  return `<section class="panel"><label class="inbox-filter">${t("contact")}<select id="message-mode"><option value="ALL" ${state.messageMode === "ALL" ? "selected" : ""}>${t("all")}</option><option value="PREVIEW" ${state.messageMode === "PREVIEW" ? "selected" : ""}>${t("fleetPreview")}</option><option value="SCHEDULED" ${state.messageMode === "SCHEDULED" ? "selected" : ""}>${t("fleetContact")}</option></select></label>${!state.messages.length ? empty(t("emptyInbox"), t("emptyInboxText")) : state.messages.map((m) => `<article class="message-card"><div class="message-top"><h3>${h(businessName(m.entity_id))}</h3><div class="meta-row"><span class="badge mock">${h(m.channel)}</span>${badge(m.status)}</div></div><small>${h(m.entity_id)} · ${h(m.language.toUpperCase())}</small><div class="message-envelope"><strong>${h(m.sender || "Fonecta Connect · Demo")}</strong><small>${t("recipient")}: ${h(m.recipient || m.entity_id)}</small>${m.subject ? `<strong>${h(m.subject)}</strong>` : ""}<small>${t("deliveryDemo")}</small></div><div class="bubble channel-${h(m.channel.toLowerCase())}">${h(m.text).replace(/\n/g, "<br>")}</div><small>${t("simulation")} ${m.scheduled_at ? " · " + t("scheduled") + " " + h(dateLabel(m.scheduled_at)) : ""}</small>${m.owner_entry_path ? `<div class="actions"><a class="owner-link" href="${h(APP_BASE + m.owner_entry_path)}" target="_blank" rel="noopener noreferrer">${t("openCustomer")} ↗</a></div>` : ""}</article>`).join("")}${pager("messages", state.messageOffset, state.messageTotal)}</section>`;
}
function bindCommon() {
  document.querySelector("#search")?.addEventListener("input", (e) => {
    clearTimeout(bindCommon.timer);
    const q = e.target.value;
    bindCommon.timer = setTimeout(
      () => loadBusinesses(q).catch((e) => toast(errorText(e))),
      250,
    );
  });
  document
    .querySelector("#business")
    ?.addEventListener("change", (e) => (state.selected = e.target.value));
  document
    .querySelector("#target-date")
    ?.addEventListener("change", (e) => (state.date = e.target.value));
}
async function loadBusinesses(q = "FI-D") {
  const d = await api(
    "/api/v1/operator/businesses?q=" +
      encodeURIComponent(q) +
      "&limit=100&offset=0",
  );
  state.businesses = d.items;
  const el = document.querySelector("#business");
  if (el) el.innerHTML = businessOptions();
}
async function refreshCases() {
  state.cases = (await api("/api/v1/operator/cases")).items;
}
async function run(scope = "EXPLICIT_DATES") {
  state.selected = document.querySelector("#business")?.value || state.selected;
  state.date = document.querySelector("#target-date")?.value || state.date;
  const body = { scope, entity_ids: [state.selected] };
  if (scope === "EXPLICIT_DATES") body.dates = [state.date];
  await api("/api/v1/operator/cycles", "POST", body);
  await refreshCases();
  state.tab = "overview";
  render();
}
async function openCase(id) {
  const c = state.cases.find((c) => c.case_id === id);
  if (!c) return;
  const p = c.proposal_id
    ? await api("/api/v1/proposals/" + encodeURIComponent(c.proposal_id))
    : null;
  if (p && p.decision_status !== "PENDING")
    p._result = await api(
      "/api/v1/proposals/" + encodeURIComponent(p.proposal_id) + "/result",
    );
  dialog.innerHTML = `<div class="modal-head"><div><p class="eyebrow">${h(c.entity_id)} · ${h(dateLabel(c.target_date))}</p><h2>${h(p?.business_name || businessName(c.entity_id))}</h2></div><button class="ghost" data-close aria-label="${t("close")}">✕</button></div><div class="meta-row">${badge(c.action)}${badge(c.priority)}${p ? `<span class="badge mock">${t("confidence")}: ${t(p.confidence)}</span>` : ""}</div><p>${h(reasonText(c))}</p>${p ? scheduleView(p) : `<div class="notice">${t("noOutreach")}${c.status === "DEFER" ? "<br>" + t("noHistory") : ""}</div>`}${p?.decision_status === "PENDING" ? `<div class="actions"><button class="primary" data-message="${h(p.proposal_id)}" data-mode="PREVIEW" data-entity="${h(c.entity_id)}">${t("preview")}</button><button data-message="${h(p.proposal_id)}" data-mode="SCHEDULED" data-entity="${h(c.entity_id)}">${t("schedule")}</button>${state.cases.filter((x) => x.entity_id === c.entity_id && x.proposal_id).length > 1 ? `<button data-bundle="${h(c.entity_id)}">${t("bundlePreview")}</button>` : ""}</div>` : p ? renderResult(p, p._result) : ""}<hr><h3>${t("evidence")}</h3>${evidence(c.evidence)}${c.gaps?.length ? `<h3>${t("gaps")}</h3><ul>${c.gaps.map((g) => `<li><small>${h(g)}</small></li>`).join("")}</ul>` : ""}${c.recheck_trigger ? `<small>${t("recheck")}: ${h(c.recheck_trigger)}</small>` : ""}${c.action === "FLAG" ? `<hr><h3>${t("resolve")}</h3><div class="stack"><label>${t("resolution")}<select id="resolution"><option value="NEEDS_OWNER">${t("needsOwner")}</option><option value="RESOLVED">${t("resolved")}</option><option value="DISMISSED">${t("dismissed")}</option></select></label><label>${t("note")}<textarea id="review-note" placeholder="${t("noteHint")}"></textarea></label><small>${t("dates")}: ${h(c.affected_dates.join(", "))}</small><button data-resolve="${h(c.issue_id)}" data-case-id="${h(c.case_id)}">${t("save")}</button></div>` : ""}`;
  dialog.showModal();
}
async function message(id, mode, entity) {
  await api(
    "/api/v1/operator/messages",
    "POST",
    { entity_id: entity, proposal_ids: [id], delivery_mode: mode },
    key(),
  );
  dialog.close();
  state.messageMode = mode;
  state.messageOffset = 0;
  await refreshMessages();
  state.tab = "inbox";
  render();
  toast(t(mode === "PREVIEW" ? "previewReady" : "queued"));
}
async function initCustomer() {
  const hash = new URLSearchParams(location.hash.slice(1)),
    token = hash.get("token");
  if (token) {
    history.replaceState(null, "", location.pathname + location.search);
    state.owner = await api("/api/v1/session", "POST", { token });
    sessionStorage.setItem(OWNER_STORAGE, JSON.stringify(state.owner));
  } else {
    try {
      state.owner = JSON.parse(
        sessionStorage.getItem(OWNER_STORAGE) || "null",
      );
    } catch {}
  }
  if (state.owner) {
    await refreshOwner();
  }
  render();
}
async function refreshOwner() {
  state.proposals = await Promise.all(
    state.owner.proposal_ids.map((id) =>
      api("/api/v1/proposals/" + encodeURIComponent(id)),
    ),
  );
  state.preferences = await api(
    "/api/v1/businesses/" +
      encodeURIComponent(state.owner.entity_id) +
      "/contact-preferences",
  );
  state.permissions = (
    await api(
      "/api/v1/businesses/" +
        encodeURIComponent(state.owner.entity_id) +
        "/standing-permissions",
    )
  ).items;
  for (const p of state.proposals) {
    p._result = await api(
      "/api/v1/proposals/" + encodeURIComponent(p.proposal_id) + "/result",
    );
  }
}
function renderCustomer() {
  if (state.owner && isWhatsAppView()) return renderWhatsAppCustomer();
  app.innerHTML = `<main class="customer-shell"><header class="customer-header"><div class="customer-brand">${brand()}</div>${language()}</header>${ownerJourney()}<div class="customer-context"><span class="badge mock">● ${t(state.proposals[0]?.mode === "sandbox" ? "sandbox" : "mock")}</span></div>${!state.owner ? `<div class="customer-card">${empty(t("noSession"), "")}<a href="${APP_BASE}/">${t("returnHome")}</a></div>` : `<p class="eyebrow">${h(state.proposals[0]?.business_name || state.owner.entity_id)}</p><h1>${t("customerWelcome")}</h1><p class="muted">${t("customerIntro")}</p>${state.proposals.length > 1 ? `<div class="notice">${t("bundle")}</div>` : ""}${state.proposals.map(renderProposal).join("")}<a class="journey-return" href="${APP_BASE}/">← ${APP_BASE ? "Back to workspace" : "Back to the guided demo"}</a>${renderSettings()}`}<div class="footer-note">${t("simulation")}</div></main>`;
  bindCommon();
}
function renderProposal(p) {
  const decided = p.decision_status !== "PENDING";
  const r = p._result;
  return `<article class="customer-card" id="proposal-${h(p.proposal_id)}"><div class="meta-row">${badge(p.decision_status)}<small>${h(dateLabel(p.change.date || p.change.effective_from || p.change.reopen_date, p.timezone))} · ${h(p.timezone)}</small></div><h2>${h(holidayLabel(p.day_key))}</h2>${scheduleView(p)}<p class="lead">${h(reasonText(p))}</p><details class="details"><summary>${t("openEvidence")}</summary><div>${evidence(p.evidence)}</div></details>${decided ? renderResult(p, r) : `${p.mode === "sandbox" ? `<div class="notice warn">${t("realTarget")}: ${h(p.target_business_name || "")} · ${h(p.target_entity_id || "")}<br>${t("sandboxEvidence")}: ${h(p.business_name)} (${h(p.entity_id)})<br>${t("approve")} → Yext</div>` : ""}<div class="actions"><button class="primary" data-decision="APPROVE" data-id="${h(p.proposal_id)}">✓ ${t("approve")}</button><button data-edit="${h(p.proposal_id)}">${t("edit")}</button><button class="ghost" data-decision="REJECT" data-id="${h(p.proposal_id)}">${t("reject")}</button></div><p class="decision-hint">These choices work with or without the reply assistant.</p>${state.editing === p.proposal_id ? renderEdit(p) : ""}<details class="details reply-panel" ${state.replyText[p.proposal_id] ? "open" : ""}><summary>${t("textLabel")}</summary><div class="stack"><label><span class="sr-only">${t("textLabel")}</span><textarea maxlength="2000" id="text-${h(p.proposal_id)}" data-reply-text="${h(p.proposal_id)}" placeholder="${t("textHint")}" ${state.replyBusy[p.proposal_id] ? "disabled" : ""}>${h(state.replyText[p.proposal_id] || "")}</textarea></label><small class="reply-privacy">${t("replyPrivacy")}</small><button data-interpret="${h(p.proposal_id)}" ${state.replyBusy[p.proposal_id] ? "disabled" : ""}>${t(state.replyBusy[p.proposal_id] ? "replyWaiting" : "interpret")}</button><div aria-live="polite">${renderDraft(p)}</div></div></details>`}</article>`;
}
function renderEdit(p) {
  const c = p.change,
    id = p.proposal_id;
  const fields =
    c.kind === "DATE_HOURS"
      ? `<label>${t("editLabel")}<input id="edit-hours-${h(id)}" value="${h(c.hours)}" placeholder="07:30-15:00"></label>`
      : c.kind === "REOPEN_DATE"
        ? `<label>${t("date")}<input type="date" id="edit-reopen-${h(id)}" value="${h(c.reopen_date)}"></label>`
        : Object.entries(c.weekdays)
            .map(
              ([day, value]) =>
                `<label>${h(day)}<input id="edit-weekday-${h(day)}-${h(id)}" value="${h(value)}"></label>`,
            )
            .join("");
  return `<div class="edit-form">${fields}<small>${t("editHint")}</small><div class="actions"><button class="primary" data-edit-preview="${h(id)}">${t("editPreview")}</button><button data-edit-cancel>${t("cancel")}</button></div></div>`;
}

function renderDraft(p) {
  const d = state.drafts[p.proposal_id];
  if (!d) return "";
  return `<div class="notice ${d.status === "READY" ? "" : "warn"}" data-reply-status="${h(d.status)}">${h(draftText(d))}<br><small>${t("previewOnly")}${d.interpretation ? ` · ${h(d.interpretation.provider)} · ${(d.interpretation.latency_ms / 1000).toFixed(1)}s` : ""}</small>${d.status === "READY" ? `<div class="actions"><button class="primary" data-draft="${h(p.proposal_id)}">${t("confirmReply")}</button></div>` : d.status === "UNAVAILABLE" || d.interpretation?.error_code === "NOT_CONFIGURED" ? `<div class="actions"><button data-edit="${h(p.proposal_id)}">Enter hours manually</button></div>` : ""}</div>`;
}
function renderResult(p, r, refreshContext = IS_OWNER ? "owner" : "case") {
  const refreshButton = refreshContext === "demo" ? ""
    : `<button class="small" ${refreshContext === "owner" ? "data-refresh-owner" : `data-case="${h(p.case_id)}"`}>${t("refresh")}</button>`;
  const ok = r?.application_status === "SUCCEEDED",
    rejected = p.decision_status === "REJECTED";
  const title = ok
    ? "verified"
    : rejected
      ? "rejected"
      : ["FAILED", "CONFLICT", "REVIEW_REQUIRED"].includes(
            r?.application_status,
          )
        ? "failed"
        : "pending";
  return `<hr><div class="result-icon">${ok ? "✓" : rejected ? "−" : "◷"}</div><h2>${t(title)}</h2><div class="meta-row">${badge(r?.application_status || "NOT_STARTED")}</div>${r?.final_change ? `<p><strong>${h(changeText(r.final_change))}</strong></p>` : ""}<p class="lead">${ok ? t("resultExplain") : rejected ? t("notStarted") : h(r?.error_code || "")}</p>${r?.mode === "sandbox" && ok ? `<div class="notice" data-sandbox-verified>${t("liveVerified")} · ${h(r.target_entity_id)}</div>` : ""}${r?.verified_at ? `<small>${h(dateLabel(r.verified_at))}</small>` : ""}${r?.publishers?.length ? `<h3 style="margin-top:24px">${t("estimate")}</h3><ul class="publisher-list">${r.publishers.map((pub) => `<li><span>${h(pub.publisher_name)}</span><small>${pub.expected_live_by ? h(dateLabel(pub.expected_live_by)) : t("unknown")}<br>${h(pub.listing_status)}</small></li>`).join("")}</ul><div class="notice">${t("estimateNote")}</div>` : ""}${refreshButton}`;
}
function renderSettings() {
  const p = state.preferences;
  if (!p) return "";
  return `<section class="customer-card"><h2>${t("settings")}</h2><small>${t("channel")}: ${h(p.preferred_channel)} · English</small>${p.source_opted_out ? `<div class="notice warn">${t("optout")}</div>` : ""}<div class="settings-grid" style="margin-top:20px"><label>${t("frequency")}<select id="frequency">${["TWICE_MONTHLY", "MONTHLY", "PAUSED"].map((f) => `<option value="${f}" ${p.frequency === f ? "selected" : ""}>${t(f)}</option>`).join("")}</select></label><button id="save-frequency">${t("save")}</button></div><p><small>${t("nextContact")}: ${p.next_contact_at ? h(dateLabel(p.next_contact_at)) : t("PAUSED")}</small></p><details class="details"><summary>${t("permissionTitle")}</summary><div class="stack"><small>${t("permissionHelp")}</small>${state.permissions
    .filter((x) => x.status === "ACTIVE")
    .map(
      (pm) =>
        `<div class="permission"><span>${h(pm.day_keys.join(", "))}<br><small>${t("permissionExpiry")}: ${h(dateLabel(pm.expires_at))}</small></span><button class="small" data-revoke="${h(pm.permission_id)}">${t("revoke")}</button></div>`,
    )
    .join(
      "",
    )}<label class="check-label"><input type="checkbox" id="permission-check">${t("permissionCheck")}</label><button id="grant-permission">${t("grant")}: ${h(state.proposals[0]?.day_key || "")}</button></div></details></section>`;
}
async function decide(id, decision, extra = {}) {
  const p = state.proposals.find((x) => x.proposal_id === id);
  await api(
    `/api/v1/proposals/${encodeURIComponent(id)}/decisions`,
    "POST",
    { proposal_version: p.version, decision, ...extra },
    key(),
  );
  state.editing = null;
  await refreshOwner();
  render();
}
async function interpret(id) {
  if (state.replyBusy[id]) return;
  const text = document.getElementById("text-" + id).value;
  if (!text.trim() || text.length > 2000) throw new Error(t("replyInvalid"));
  state.replyText[id] = text;
  delete state.drafts[id];
  state.replyBusy[id] = true;
  const reopen = () => {
    const card = document.getElementById("proposal-" + id);
    const panel = card?.querySelector("details.reply-panel");
    if (panel) panel.open = true;
  };
  render();
  reopen();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    state.drafts[id] = await api(
      `/api/v1/proposals/${encodeURIComponent(id)}/interpret`,
      "POST",
      { text, language: lang },
      undefined,
      controller.signal,
    );
  } catch (e) {
    if (e.name === "AbortError" || e instanceof TypeError) {
      state.drafts[id] = {
        status: "UNAVAILABLE",
        intent: "UNKNOWN",
        missing_fields: [],
        interpretation: {
          provider: "GEMINI",
          latency_ms: 0,
          error_code: e.name === "AbortError" ? "TIMEOUT" : "NETWORK_ERROR",
        },
      };
    } else throw e;
  } finally {
    clearTimeout(timer);
    state.replyBusy[id] = false;
    render();
    reopen();
  }
}
app.addEventListener("input", (e) => {
  if (e.target.dataset.replyText) {
    const id = e.target.dataset.replyText;
    state.replyText[id] = e.target.value;
    delete state.drafts[id];
    const preview = document.querySelector(
      `#proposal-${CSS.escape(id)} [data-reply-status]`,
    );
    if (preview) preview.remove();
  }
});
async function confirmDraft(id) {
  const d = state.drafts[id];
  if (d.decision_draft) {
    await api(
      `/api/v1/proposals/${encodeURIComponent(id)}/decisions`,
      "POST",
      d.decision_draft,
      key(),
    );
  } else if (d.preference_draft) {
    await api(
      `/api/v1/businesses/${encodeURIComponent(state.owner.entity_id)}/contact-preferences`,
      "PATCH",
      d.preference_draft,
      key(),
    );
  } else if (d.permission_draft) {
    await api(
      `/api/v1/businesses/${encodeURIComponent(state.owner.entity_id)}/standing-permissions`,
      "POST",
      d.permission_draft,
      key(),
    );
  }
  delete state.drafts[id];
  await refreshOwner();
  render();
}

async function openReset() {
 dialog.innerHTML = `<div class="modal-head"><h2>${t("resetTitle")}</h2><button class="ghost" data-close>✕</button></div><p>${t("resetLoading")}</p>`;
 dialog.showModal();
 try {
  const p = await api("/api/v1/operator/reset");
  state.resetPreview = p;
  state.resetKey = key();
  dialog.innerHTML = `<div class="modal-head"><h2>${t("resetTitle")}</h2><button class="ghost" data-close>✕</button></div><div class="notice warn"><strong>${p.mode === "sandbox" ? t("realTarget") + ": " + h(p.target_entity_id) : p.business_count + " " + t("fleetCompanies")}</strong><p>${t(p.mode === "sandbox" ? "resetSandbox" : "resetMock")}</p>${p.mode === "sandbox" && !Object.keys(p.baseline_hours).length ? `<p>${t("resetOriginalHours")}: ${t("notRegistered")}</p>` : ""}</div><h3>${t("resetCounts")}</h3><p>${t("resetCases")}: ${p.counts.cases} · ${t("resetMessages")}: ${p.counts.messages} · ${t("resetDecisions")}: ${p.counts.decisions}</p><p>${t("resetBackup")}</p>${p.recovery_required ? `<p class="notice warn">${t("resetRecover")}</p>` : ""}<div class="actions"><button class="danger" id="reset-confirm">${t("resetConfirm")}</button><button data-close>${t("cancel")}</button></div>`;
 } catch(e) {
  dialog.innerHTML = `<div class="modal-head"><h2>${t("resetTitle")}</h2><button class="ghost" data-close>✕</button></div><p class="notice warn">${h(errorText(e))}</p>`;
 }
}
async function confirmReset() {
 const p = state.resetPreview;
 try {
  await api("/api/v1/operator/reset", "POST", {confirm_reset:true,preview_token:p.preview_token}, state.resetKey);
  sessionStorage.removeItem(OWNER_STORAGE);
  sessionStorage.removeItem(demoStorageKey());
  sessionStorage.setItem("reset-complete" + APP_BASE, "1");
  location.href = APP_BASE + "/";
 } catch(e) {
  dialog.innerHTML = `<div class="modal-head"><h2>${t("resetTitle")}</h2><button class="ghost" data-close>✕</button></div><p class="notice warn">${h(errorText(e))}</p>`;
 }
}

async function exportCSV() {
  const csv = await api("/api/v1/operator/export.csv");
  const url = URL.createObjectURL(
    new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8;" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "connect_predictions_2026.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b || b.disabled || b.matches("[data-wa-composer] [type=submit]")) return;
  const old = b.innerHTML;
  try {
    b.disabled = true;
    if (b.dataset.demoAction) {
      await handleDemoAction(b.dataset.demoAction);
    } else if (b.id === "reset-open") {
      await openReset();
    } else if (b.id === "reset-confirm") {
      await confirmReset();
    } else if (b.id === "sandbox-refresh") {
      await refreshFleet(); render();
    } else if (b.id === "sandbox-demo") {
      await run();
      const c = state.cases.find(c => c.entity_id === state.selected && c.target_date === state.date && c.action === "SUGGEST");
      if (c) await message(c.proposal_id, "PREVIEW", c.entity_id);
      else toast(t("sandboxNoChange"));
    } else if (b.dataset.tab) {
      state.tab = b.dataset.tab;
      state.filter = "ALL";
      state.caseOffset = 0;
      if (state.tab === "demo") await restoreDemo();
      if (state.tab === "inbox") {
        state.messageOffset = 0;
        if (state.fleet?.contact_status === "COMPLETED")
          state.messageMode = state.fleet.contact_mode;
        await refreshMessages();
      }
      render();
    } else if (b.dataset.filter) {
      state.filter = b.dataset.filter;
      state.caseOffset = 0;
      render();
    } else if (b.id === "fleet-start") {
      const body = { scope: state.fleetScope };
      if (body.scope === "EXPLICIT_DATE") body.date = state.fleetDate;
      state.fleet = await api("/api/v1/operator/fleet-runs", "POST", body);
      render();
      scheduleFleetPoll();
    } else if (b.dataset.fleetContact) {
      state.fleet = await api(
        `/api/v1/operator/fleet-runs/${encodeURIComponent(state.fleet.run_id)}/contacts`,
        "POST",
        { delivery_mode: b.dataset.fleetContact },
      );
      render();
      scheduleFleetPoll();
    } else if (b.dataset.pageKind) {
      const next = Number(b.dataset.offset);
      if (b.dataset.pageKind === "cases") state.caseOffset = next;
      else {
        state.messageOffset = next;
        await refreshMessages();
      }
      render();
    } else if (b.dataset.example) {
      state.selected = b.dataset.example;
      state.date = "2026-12-24";
      render();
      await run();
    } else if (b.id === "run") {
      b.innerHTML = `<span class="spinner"></span>${t("busy")}`;
      await run();
    } else if (b.id === "operational") await run("OPERATIONAL");
    else if (b.id === "export") await exportCSV();
    else if (b.dataset.case) await openCase(b.dataset.case);
    else if (b.hasAttribute("data-close")) dialog.close();
    else if (b.dataset.bundle) {
      const eid = b.dataset.bundle;
      const ps = await Promise.all(
        state.cases
          .filter((x) => x.entity_id === eid && x.proposal_id)
          .map((x) =>
            api("/api/v1/proposals/" + encodeURIComponent(x.proposal_id)),
          ),
      );
      const ids = ps
        .filter((x) => x.decision_status === "PENDING")
        .map((x) => x.proposal_id);
      if (!ids.length) throw new Error(t("noProposal"));
      await api(
        "/api/v1/operator/messages",
        "POST",
        { entity_id: eid, proposal_ids: ids, delivery_mode: "PREVIEW" },
        key(),
      );
      dialog.close();
      await refreshMessages();
      state.tab = "inbox";
      render();
    } else if (b.dataset.message)
      await message(b.dataset.message, b.dataset.mode, b.dataset.entity);
    else if (b.dataset.resolve) {
      const note = document.getElementById("review-note").value.trim();
      if (!note) throw new Error(t("required"));
      const c = state.cases.find((x) => x.case_id === b.dataset.caseId);
      await api(
        "/api/v1/operator/issues/" +
          encodeURIComponent(b.dataset.resolve) +
          "/resolve",
        "POST",
        {
          resolution: document.getElementById("resolution").value,
          note,
          evidence: c.evidence,
        },
        key(),
      );
      dialog.close();
      await refreshCases();
      render();
      toast(t("reviewSaved"));
    } else if (b.dataset.decision)
      await decide(b.dataset.id, b.dataset.decision);
    else if (b.dataset.edit) {
      state.editing = b.dataset.edit;
      render();
    } else if (b.hasAttribute("data-edit-cancel")) {
      state.editing = null;
      render();
    } else if (b.dataset.editPreview) {
      const p = state.proposals.find(
          (x) => x.proposal_id === b.dataset.editPreview,
        ),
        c =
          p.change.kind === "DATE_HOURS"
            ? {
                ...p.change,
                hours: document
                  .getElementById("edit-hours-" + p.proposal_id)
                  .value.trim(),
              }
            : p.change.kind === "REOPEN_DATE"
              ? {
                  ...p.change,
                  reopen_date: document.getElementById(
                    "edit-reopen-" + p.proposal_id,
                  ).value,
                }
              : {
                  ...p.change,
                  weekdays: Object.fromEntries(
                    Object.keys(p.change.weekdays).map((day) => [
                      day,
                      document
                        .getElementById(
                          "edit-weekday-" + day + "-" + p.proposal_id,
                        )
                        .value.trim(),
                    ]),
                  ),
                };
      state.drafts[p.proposal_id] = {
        status: "READY",
        preview: changeText(c),
        decision_draft: {
          decision: "EDIT",
          proposal_version: p.version,
          edited_change: c,
          confirmed: true,
        },
      };
      dialog.innerHTML = `<div class="modal-head"><h2>${t("editPreview")}</h2><button class="ghost" data-close>✕</button></div><p>${h(dateLabel(c.date || c.effective_from || c.reopen_date))}</p><h2>${h(changeText(c))}</h2><p class="muted">${t("previewOnly")}</p><button class="primary" data-confirm-edit="${h(p.proposal_id)}">${t("confirmEdit")}</button>`;
      dialog.showModal();
    } else if (b.dataset.confirmEdit) {
      await confirmDraft(b.dataset.confirmEdit);
      dialog.close();
    } else if (b.dataset.interpret) await interpret(b.dataset.interpret);
    else if (b.dataset.draft) await confirmDraft(b.dataset.draft);
    else if (b.hasAttribute("data-refresh-owner")) {
      await refreshOwner();
      render();
    } else if (b.id === "save-frequency") {
      await api(
        "/api/v1/businesses/" +
          encodeURIComponent(state.owner.entity_id) +
          "/contact-preferences",
        "PATCH",
        {
          version: state.preferences.version,
          frequency: document.getElementById("frequency").value,
        },
        key(),
      );
      await refreshOwner();
      render();
      toast(t("saved"));
    } else if (b.id === "grant-permission") {
      if (!document.getElementById("permission-check").checked)
        throw new Error(t("required"));
      const p = state.proposals[0];
      const expiry = new Date(
        new Date(p.created_at).getTime() + 364 * 86400000,
      ).toISOString();
      await api(
        "/api/v1/businesses/" +
          encodeURIComponent(state.owner.entity_id) +
          "/standing-permissions",
        "POST",
        {
          day_keys: [p.day_key],
          change_kind: "DATE_HOURS",
          purpose: "CORRECTION",
          expires_at: expiry,
          confirmed: true,
        },
        key(),
      );
      await refreshOwner();
      render();
      toast(t("saved"));
    } else if (b.dataset.revoke) {
      await api(
        "/api/v1/businesses/" +
          encodeURIComponent(state.owner.entity_id) +
          "/standing-permissions/" +
          encodeURIComponent(b.dataset.revoke),
        "DELETE",
        undefined,
        key(),
      );
      await refreshOwner();
      render();
      toast(t("saved"));
    }
  } catch (err) {
    toast(errorText(err));
  } finally {
    if (b.isConnected) {
      b.disabled = false;
      b.innerHTML = old;
    }
  }
});
dialog.addEventListener("click", (e) => {
  if (e.target === dialog && e.clientX < dialog.getBoundingClientRect().left)
    dialog.close();
});
(async () => {
  try {
    if (IS_OWNER) await initCustomer();
    else {
      render();
      state.health = await api("/api/v1/health");
      await loadBusinesses();
      await refreshCases();
      await refreshFleet();
      if (!APP_BASE) await restoreDemo();
      render();
      if (sessionStorage.getItem("reset-complete" + APP_BASE)) { sessionStorage.removeItem("reset-complete" + APP_BASE); toast(t("resetSuccess")); }
    }
  } catch (e) {
    render();
    toast(errorText(e));
  }
})();
