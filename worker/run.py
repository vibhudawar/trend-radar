"""CLI entrypoint — run a full refresh for one project. Used manually and (later) by cron.

Usage: python run.py <project_id>
"""
import sys

from trendradar.pipeline import run_project

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python run.py <project_id>")
    out = run_project(sys.argv[1])
    print(f"done: project={out['project_id']} credits_used={out['credits_used']}")
