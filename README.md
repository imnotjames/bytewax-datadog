[![PyPI](https://img.shields.io/pypi/v/bytewax-datadog.svg?style=flat-square)][pypi-package]

# Bytewax Datadog

[Datadog][datadog] conectors for [Bytewax][bytewax].

This connector offers 1 source and 1 sink.

* `LogSink` - writes Datadog logs.
* `LogSource` - reads Datadog logs.

## Installation

This package is available via [PyPi][pypi-package] as
`bytewax-datadog` and can be installed via your package manager of choice.

## Usage

### Logs Source

```python
from bytewax_datadog import LogSource
from bytewax.connectors.stdio import StdOutSink

import bytewax.operators as op
from bytewax.dataflow import Dataflow

flow = Dataflow("datadog_example")
flow_input = op.input("input", flow, LogSource.from_environment("example query"))
op.output("output", flow_input, StdOutSink())
```

### Logs Sink

```python
from bytewax_datadog import LogSink, CreateLogEntry
from bytewax.testing import TestingSource

import bytewax.operators as op
from bytewax.dataflow import Dataflow

flow = Dataflow("datadog_example")
flow_input = op.input("input", flow, TestingSource([
    CreateLogEntry(
        hostname="localhost",
        service="example-service",
        message="Hello World!",
    )
]))
op.output("output", flow_input, LogSink.from_environment("bytewax-datadog"))
```

## License

Licensed under the [MIT License](./LICENSE)

[datadog]: https://www.datadog.com
[bytewax]: https://bytewax.io
[pypi-package]: https://pypi.org/project/bytewax-datadog