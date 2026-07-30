import time
from datetime import datetime

from dotenv import load_dotenv

import api_client
import campaign_processor
import lead_sourcing_processor
import notifier
import reply_checker
import trigger_processor
from keep_alive import keep_alive
from scheduler import Scheduler

load_dotenv()

sched = Scheduler()

# IMAP servers rate-limit/throttle connections harder than a plain HTTP
# poll, so the reply check runs less often than the send/AI cycle — Django
# still decides everything about *what* counts as a reply, this only
# decides *how often* to ask.
REPLY_CHECK_EVERY_N_TICKS = 3


def run_one_cycle(tick):
    config = api_client.fetch_config()

    try:
        notifier.push_notifications(config, api_client.report_notifications_pushed)
    except Exception as e:
        print(f"Notifier error: {e}")

    if sched.is_due(REPLY_CHECK_EVERY_N_TICKS) and config.get("imap_config"):
        try:
            reply_checker.check_replies(config["imap_config"], api_client.report_reply_detected)
        except Exception as e:
            print(f"Reply check error: {e}")
            notifier.push_error(config, "Reply check", str(e))

    try:
        campaign_processor.process_ai_jobs(config)
    except Exception as e:
        print(f"AI job processing error: {e}")
        notifier.push_error(config, "AI job processing", str(e))

    try:
        campaign_processor.process_sendable()
    except Exception as e:
        print(f"Send-cycle error: {e}")
        notifier.push_error(config, "Send cycle", str(e))

    try:
        lead_sourcing_processor.process_lead_sourcing()
    except Exception as e:
        print(f"Lead sourcing error: {e}")
        notifier.push_error(config, "Lead sourcing", str(e))

    try:
        trigger_processor.process_pending_triggers(config)
    except Exception as e:
        print(f"Trigger processing error: {e}")
        notifier.push_error(config, "Trigger processing", str(e))

    return config


def auto_loop():
    while True:
        tick = sched.advance()
        try:
            config = run_one_cycle(tick)
            interval = config.get("poll_interval", 60)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Could not reach Django API: {e}")
            interval = 15

        time.sleep(interval)


if __name__ == "__main__":
    print("Launching outreach worker...")
    keep_alive()
    auto_loop()
