# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import os
import traceback
import logging

loglevel = os.environ['LOGLEVEL']
numeric_level = getattr(logging, loglevel.upper(), logging.INFO)
LOGGER = logging.getLogger()
LOGGER.setLevel(numeric_level)
LOGGER.debug("Set log level to " + str(numeric_level))

docdb = boto3.client('docdb')
ssm = boto3.client('ssm')

def handler(event, context):
    LOGGER.debug("Got event " + json.dumps(event))

    cluster_id = event['pathParameters']['scalableTargetDimensionId']
    LOGGER.info("Getting status for cluster " + cluster_id)

    try:
        LOGGER.debug("Getting current value of desired size param")
        param_name = "DesiredSize-" + cluster_id
        r = ssm.get_parameter( Name= param_name)
        desired_count = int(r['Parameter']['Value'])
        LOGGER.debug("Got current value of desired size param : {0}".format(str(desired_count)))

        LOGGER.debug("Getting cluster status")
        r = docdb.describe_db_clusters( DBClusterIdentifier=cluster_id)
        cluster_info = r['DBClusters'][0]
        readers = []
        for member in cluster_info['DBClusterMembers']:
            member_id = member['DBInstanceIdentifier']
            member_type = member['IsClusterWriter']

            if member_type == False:
                readers.append(member_id)
        LOGGER.debug("Found {0} readers".format(str(len(readers))))

        LOGGER.debug("Getting cluster instance status")
        r = docdb.describe_db_instances(Filters=[{'Name':'db-cluster-id','Values': [cluster_id]}])
        instances = r['DBInstances']
        num_available = 0
        num_pending = 0
        num_failed = 0
        for i in instances:
            instance_id = i['DBInstanceIdentifier']
            if instance_id in readers:
                instance_status = i['DBInstanceStatus']
                if instance_status == 'available':
                    num_available = num_available + 1
                if instance_status in ['creating', 'deleting', 'starting', 'stopping']:
                    num_pending = num_pending + 1
                if instance_status == 'failed':
                    num_failed = num_failed + 1
        LOGGER.debug("Found {0} readers available, {1} pending, and {2} failed".format(str(num_available), str(num_pending), str(num_failed)))

        scalingStatus = 'Successful' # Pending, InProgress, Failed
        if num_available != desired_count:
            scalingStatus = 'Pending'
        if num_pending > 0:
            scalingStatus = 'InProgress'
        if num_failed > 0:
            scalingStatus = 'Failed'
            
        LOGGER.info("Scaling status: {0}".format(scalingStatus))

        responseBody = {
            "actualCapacity": float(num_available),
            "desiredCapacity": float(desired_count),
            "dimensionName": cluster_id,
            "resourceName": cluster_id,
            "scalableTargetDimensionId": cluster_id,
            "scalingStatus": scalingStatus,
            "version": "1.0"
        }
        response = {
            'statusCode': 200,
            'headers': {"content-type": "application/json"},
            'body': json.dumps(responseBody)
        }
        LOGGER.debug("Response: " + json.dumps(response))
        return response
    except Exception as e:
        trc = traceback.format_exc()
        response = {
            'statusCode': 404,
            'body': str(e)
        }
        LOGGER.debug("Response: " + json.dumps(response))
        return response
