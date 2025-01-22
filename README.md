# iKlayout
This is a port of [kLayout](https://www.klayout.de/) to a python notebook widget using matplotlib to enable interactive klayouts in notebooks.

## Installation

`pip install iklayout`

## Usage

```python
%matplotlib widget

import iklayout

path = "/path/to/your/gds.gds"

iklayout.show(path)
```