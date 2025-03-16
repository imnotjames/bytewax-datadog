from typing import NamedTuple, Self, Sequence

from bytewax.outputs import DynamicSink, StatelessSinkPartition
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.content_encoding import ContentEncoding
from datadog_api_client.v2.model.http_log import HTTPLog
from datadog_api_client.v2.model.http_log_item import HTTPLogItem


class CreateLogEntry(NamedTuple):
    hostname: str

    service: str

    message: str

    source: str | None = None

    tags: Sequence[str] = tuple()


MAX_CHUNK_LENGTH = 500


class LogSinkPartition(StatelessSinkPartition[CreateLogEntry]):
    def __init__(
        self,
        client: ApiClient,
        default_source: str | None = None,
        extra_tags: Sequence[str] = tuple(),
    ):
        self._logs_client = LogsApi(client)
        self._default_source = default_source
        self._extra_tags = ",".join(extra_tags)

    def _get_log_item(self, item: CreateLogEntry) -> HTTPLogItem:
        log_item = HTTPLogItem(
            ddtags=",".join(item.tags),
            hostname=item.hostname,
            service=item.service,
            message=item.message,
        )

        if item.source is not None:
            log_item.ddsource = item.source
        elif self._default_source is not None:
            log_item.ddsource = item.source

        return log_item

    def _chunk_batch(self, items: Sequence[CreateLogEntry], size: int):
        """Prepare batch for sending to Datadog.

        This attempts to ensure that the data we are sending
        to datadog is the appropriate size.  Datadog's log ingestion
        endpoint has a limit on the number of logs that may be
        submitted at once.
        """
        for i in range(0, len(items), size):
            yield HTTPLog([self._get_log_item(item) for item in items[i : i + size]])

    def write_batch(self, items: Sequence[CreateLogEntry]):
        for batch_body in self._chunk_batch(items, MAX_CHUNK_LENGTH):
            self._logs_client.submit_log(
                body=batch_body,
                content_encoding=ContentEncoding.GZIP,
                ddtags=self._extra_tags,
            )


class LogSink(DynamicSink[CreateLogEntry]):
    def __init__(
        self,
        client: ApiClient,
        default_source: str | None = None,
        extra_tags: Sequence[str] = tuple(),
    ):
        self._client = client
        self._default_source = default_source
        self._extra_tags = extra_tags

    @classmethod
    def from_environment(cls, source: str, extra_tags: Sequence[str] = tuple()) -> Self:
        # The datadog client does some sort of magic to retrieve this
        # from the environment.  I have to assume it's right?
        configuration = Configuration()
        client = ApiClient(configuration)

        return cls(client, default_source=source, extra_tags=extra_tags)

    def list_parts(self) -> list[str]:
        return ["logs"]

    def build(
        self, step_id: str, worker_index: int, worker_count: int
    ) -> LogSinkPartition:
        return LogSinkPartition(
            self._client,
            default_source=self._default_source,
            extra_tags=self._extra_tags,
        )


__all__ = (
    "CreateLogEntry",
    "LogSinkPartition",
    "LogSink",
)
