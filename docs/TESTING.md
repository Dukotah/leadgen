# Testing

Run the suite, then the coverage report (config in `.coveragerc`):

```
pip install coverage; coverage run -m pytest leadgen/tests; coverage report
```

The data-source tests are fully offline: `leadgen/tests/test_sources.py` covers the
pure helpers and `leadgen/tests/test_sources_recorded.py` feeds canned ("recorded")
responses to the requests-based collectors, so parsing is exercised with no network.
