import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: hits the real Yext sandbox (needs RUN_INTEGRATION=1 + YEXT_* env)")
