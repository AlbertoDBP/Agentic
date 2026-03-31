from app import jobs


def test_job_data_quality_scan_exists():
    assert callable(getattr(jobs, "job_data_quality_scan", None))


def test_job_data_quality_retry_exists():
    assert callable(getattr(jobs, "job_data_quality_retry", None))


def test_job_data_quality_promote_exists():
    assert callable(getattr(jobs, "job_data_quality_promote", None))
