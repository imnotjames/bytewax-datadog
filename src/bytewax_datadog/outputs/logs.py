from typing import List, NamedTuple, Self, Sequence

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


class LogSinkPartition(StatelessSinkPartition[CreateLogEntry]):
    def __init__(
        self,
        client: ApiClient,
        default_source: str,
        extra_tags: Sequence[str] = tuple(),
    ):
        self._logs_client = LogsApi(client)
        self._default_source = default_source
        self._extra_tags = ",".join(extra_tags)

    def write_batch(self, items: List[CreateLogEntry]):
        # TODO: Batch into 500-1000

        batch_body = HTTPLog(
            [
                HTTPLogItem(
                    ddsource=self._default_source if item.source is None else item.source,
                    ddtags=",".join(item.tags),
                    hostname=item.hostname,
                    service=item.service,
                    message=item.message,
                )
                for item in items
            ]
        )

        self._logs_client.submit_log(
            body=batch_body,
            content_encoding=ContentEncoding.GZIP,
            ddtags=self._extra_tags,
        )


class LogSink(DynamicSink[CreateLogEntry]):
    def __init__(
        self, client: ApiClient, default_source: str | None = None, extra_tags: Sequence[str] = tuple()
    ):
        self._client = client
        self._default_source = default_source
        self._extra_tags = extra_tags

    @classmethod
    def from_environment(cls, source: str, extra_tags: Sequence[str] = tuple()) -> Self:
        # The datadog client does some sort of magic to retrieve this
        # from the environment.  I have to assume it's right?
        # But we'll also allow passing this in.
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
