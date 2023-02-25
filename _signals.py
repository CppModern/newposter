class StopSignal:
    """A data class that should be sent to the worker when
    the conversation has to be stopped abnormally."""

    def __init__(self, reason: str = ""):
        self.reason = reason


class CancelSignal:
    """An empty class that is added to the queue whenever the
    user presses a cancel inline button."""

    pass
