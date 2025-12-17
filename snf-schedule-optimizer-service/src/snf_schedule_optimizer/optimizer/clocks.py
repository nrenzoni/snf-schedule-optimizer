import abc

import whenever


class IClock(abc.ABC):
    @abc.abstractmethod
    def now(self) -> whenever.Instant:
        pass


class SystemClock(IClock):
    def now(self) -> whenever.Instant:
        return whenever.Instant.now()
