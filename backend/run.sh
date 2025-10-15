#!/bin/bash

UVICON_OPS=$@

uvicorn $UVICON_OPS --host 0.0.0.0 --port 8000 api:app 