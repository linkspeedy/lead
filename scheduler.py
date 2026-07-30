"""Loop-cadence bookkeeping only — NOT a cron/Celery replacement. Django
alone decides what's "due" (via next_send_at, ai_personalization_status,
etc.); this just decides how often the worker asks about slower-changing
things like the IMAP mailbox, which servers rate-limit connections harder
than a plain HTTP poll."""


class Scheduler:
    def __init__(self):
        self.tick = 0

    def advance(self):
        self.tick += 1
        return self.tick

    def is_due(self, every_n_ticks):
        return self.tick % every_n_ticks == 0
