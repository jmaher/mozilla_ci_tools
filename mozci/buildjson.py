#!/usr/bin/env python
"""
This module helps with the buildjson data generated by the Release Engineering
systems: http://builddata.pub.build.mozilla.org/builddata/buildjson
"""
import datetime
import json
import logging
import os
import requests

log = logging.getLogger()

BUILDJSON_DATA = "http://builddata.pub.build.mozilla.org/builddata/buildjson"


def _daily_jobs(unix_timestamp):
    '''
       In BUILDJSON_DATA we have the information about all jobs stored
       as a gzip file per day.

       This function caches the uncompressed gzip files requested in the past.

       This function returns a json object containing all jobs for a given day.
    '''
    date = datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d')
    data_file = "builds-%s.js" % date
    log.debug("Unix timestamp value: %d represents %s" %
              (unix_timestamp, date))

    if not os.path.exists(data_file):
        url = "%s/%s.gz" % (BUILDJSON_DATA, data_file)
        log.debug("We have not been able to find on disk %s." % data_file)
        log.debug("We will now fetch %s" % url)
        # Fetch tar ball
        r = requests.get(url)
        # NOTE: requests deals with decrompressing the gzip file
        with open(data_file, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=1024):
                fd.write(chunk)

    return json.load(open(data_file))


def query_buildjson_info(claimed_at, request_id):
    """
    This function looks for a job identified by `request_id` inside of a buildjson
    file under the "builds" entry.

    Through `claimed_at`, we can determine on which day we can find the
    metadata about this job.

    If found, the returning entry will look like this (only important values
    are referenced):
    {
        "builder_id": int, # It is a unique identifier of a builder
        "starttime": int,
        "endtime": int,
        "properties": {
            "buildername": string,
            "buildid": string,
            "revision": string,
            "repo_path": string, # e.g. projects/cedar
            "log_url", string,
            "slavename": string, # e.g. t-w864-ix-120
            "blobber_files": json, # Mainly applicable to test jobs
            "packageUrl": string, # It only applies for build jobs
            "testsUrl": string,   # It only applies for build jobs
            "symbolsUrl": string, # It only applies for build jobs
        },
        "request_ids": list of ints, # Scheduling ID
        "requestime": int,
        "result": int, # Job's exit code
        "slave_id": int, # Unique identifier for the machine that run it
    }
    """
    assert type(request_id) is int
    assert type(claimed_at) is int

    status_data = _daily_jobs(claimed_at)
    builds = status_data["builds"]
    for job in builds:
        if request_id in job["request_ids"]:
            log.debug("Found %s" % str(job))
            return job
