from datetime import UTC, date, datetime, timedelta
from typing import Iterable, Mapping, NamedTuple, Optional, Self, Sequence, Union
from uuid import UUID

from bytewax.inputs import FixedPartitionedSource, StatefulSourcePartition
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.logs_api import LogsApi
from datadog_api_client.v1.models import LogsListRequest, LogsListRequestTime, LogsSort

DEFAULT_POLL_INTERVAL = 10


type LogAttributesItem = Union[
    bool,
    date,
    datetime,
    str,
    float,
    int,
    list,
    str,
    UUID,
    "LogAttributes",
    Sequence["LogAttributesItem"],
    None,
]


type LogAttributes = Mapping[str, LogAttributesItem]


class LogEntry(NamedTuple):
    id: str

    timestamp: datetime

    hostname: str

    service: str

    message: str

    attributes: LogAttributesItem

    tags: Sequence[str]


class LogSourcePartition(StatefulSourcePartition[LogEntry, str | None]):
    def __init__(
        self,
        client: ApiClient,
        filter_query: str,
        poll_interval: float | int = DEFAULT_POLL_INTERVAL,
        resume_id: Optional[str] = None,
    ):
        self._client = client
        self._cursor = resume_id

        self._filter_query = filter_query
        self._poll_interval = poll_interval

        self._logs_client = LogsApi(client)
        self._next_awake: Optional[datetime] = None

    def _get_start_at(self) -> str | None:
        """Helper to find where to start the cursor.

        This source starts at whatever "now" is by default
        but to do that we have to figure out the log record for "now"
        to start with if we haven't seen any other log records.
        """
        if self._cursor is not None:
            return self._cursor

        request = LogsListRequest(
            query=self._filter_query,
            sort=LogsSort.TIME_DESCENDING,
            time=LogsListRequestTime(
                _from=datetime.fromtimestamp(0, UTC), to=datetime.now(UTC)
            ),
            limit=1,
        )

        response = self._logs_client.list_logs(request)

        if len(response.logs) == 0:
            return None

        self._cursor = response.logs[0]["id"]
        return self._cursor

    def next_batch(self) -> Iterable[LogEntry]:
        """Retrieves the next batch of records from the datadog API.

        This function will retrieve the next batch of records after the cursor
        from the datadog v1 logs API.  It uses the v1 logs API because
        that has the `starts_at` parameter which can be used to keep our
        place while reading.
        """
        request = LogsListRequest(
            query=self._filter_query,
            sort=LogsSort.TIME_ASCENDING,
            time=LogsListRequestTime(
                _from=datetime.fromtimestamp(0, UTC),
                to=datetime.now(UTC),
            ),
        )

        start_at = self._get_start_at()
        if start_at is not None:
            request.start_at = start_at

        response = self._logs_client.list_logs(request)

        has_seen_new_records = False
        for record in response["logs"]:
            if record["id"] == self._cursor:
                continue

            has_seen_new_records = True

            self._cursor = record["id"]
            yield LogEntry(
                id=record["id"],
                hostname=record["content"]["host"],
                service=record["content"]["service"],
                timestamp=record["content"]["timestamp"],
                message=record["content"]["message"],
                attributes=record["content"]["attributes"],
                tags=record["content"]["tags"],
            )

        if has_seen_new_records:
            # If we saw new records there may be more pages.
            self._next_awake = None
        else:
            self._next_awake = datetime.now(UTC) + timedelta(
                seconds=self._poll_interval
            )

    def next_awake(self) -> Optional[datetime]:
        return self._next_awake

    def snapshot(self) -> str | None:
        return self._cursor


class LogSource(FixedPartitionedSource[LogEntry, str | None]):
    def __init__(
        self,
        client: ApiClient,
        filter_query: str,
        poll_interval: float | int = DEFAULT_POLL_INTERVAL,
    ):
        self._client = client
        self._filter_query = filter_query
        self._poll_interval = poll_interval

    @classmethod
    def from_environment(
        cls,
        filter_query: str,
        poll_interval: float | int = DEFAULT_POLL_INTERVAL,
    ) -> Self:
        # The datadog client does some sort of magic to retrieve this
        # from the environment.  I have to assume it's right?
        # But we'll also allow passing this in.
        configuration = Configuration()
        client = ApiClient(configuration)

        return cls(client, filter_query, poll_interval)

    def list_parts(self) -> list[str]:
        return [self._filter_query]

    def build_part(
        self, step_id: str, for_part: str, resume_state: Optional[str]
    ) -> LogSourcePartition:
        return LogSourcePartition(
            self._client, self._filter_query, self._poll_interval, resume_state
        )


__all__ = (
    "LogEntry",
    "LogSourcePartition",
    "LogSource",
)
