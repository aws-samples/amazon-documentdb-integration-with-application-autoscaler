# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import os
import time
import traceback
import logging
from collections import defaultdict 
import operator

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
    LOGGER.info("Scaling action for cluster " + cluster_id)

    try:
        desired_count_str = event['body']
        desired_count_j = json.loads(desired_count_str)
        desired_count = int(desired_count_j['desiredCapacity'])
        LOGGER.debug("Requested count: " + str(desired_count))
        valid_desired_count = True
        if desired_count < 1 or desired_count > 15:
            LOGGER.warn("Invalid desired count: {0} (may be happening during registration process)".format(str(desired_count)))
            valid_desired_count = False

        if valid_desired_count:
            LOGGER.debug("Updating value of desired size param")
            param_name = "DesiredSize-" + cluster_id
            r = ssm.put_parameter(
                Name=param_name,
                Value=str(desired_count),
                Type='String',
                Overwrite=True,
                AllowedPattern='^\d+$'
            )

        LOGGER.debug("Getting cluster status")
        r = docdb.describe_db_clusters( DBClusterIdentifier=cluster_id)
        cluster_info = r['DBClusters'][0]
        LOGGER.debug("Cluster status: {0}".format(cluster_info['Status']))
        if cluster_info['Status'] != 'available':
            response = {
                'statusCode': 200,
                'body': "Invalid cluster status"
            }
            LOGGER.debug("Response: " + json.dumps(response))
            return response
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
        reader_type = ''
        reader_engine = ''
        num_available = 0
        num_pending = 0
        num_failed = 0
        reader_az_cnt = defaultdict(int)
        reader_az_map = defaultdict(list)
        for i in instances:
            instance_id = i['DBInstanceIdentifier']
            if instance_id in readers:
                instance_status = i['DBInstanceStatus']
                reader_type = i['DBInstanceClass']
                reader_engine = i['Engine']
                reader_az = i['AvailabilityZone']
                reader_az_cnt[reader_az] += 1
                reader_az_map[reader_az].append(instance_id) 
                if instance_status == 'available':
                    num_available = num_available + 1
                if instance_status in ['creating', 'deleting', 'starting', 'stopping']:
                    num_pending = num_pending + 1
                if instance_status == 'failed':
                    num_failed = num_failed + 1
        LOGGER.debug("Found {0} readers available, {1} pending, and {2} failed".format(str(num_available), str(num_pending), str(num_failed)))

        scalingStatus = 'Successful' # Pending, InProgress, Failed
        if valid_desired_count:
            if num_available != desired_count:
                scalingStatus = 'Pending'
            if num_pending > 0:
                scalingStatus = 'InProgress'
            if num_failed > 0:
                scalingStatus = 'Failed'
        LOGGER.info("Scaling status: {0}".format(scalingStatus))

        if scalingStatus == 'Pending':
            LOGGER.info("Initiating scaling actions on cluster {0} since actual count {1} does not equal desired count {2}".format(cluster_id, str(num_available), str(desired_count)))
            if num_available < desired_count:
                num_to_create = desired_count - num_available
                for idx in range(num_to_create):
                    docdb.create_db_instance(
                        DBInstanceIdentifier=readers[0] + '-' + str(idx) + '-' + str(int(time.time())),
                        DBInstanceClass=reader_type,
                        Engine=reader_engine,
                        DBClusterIdentifier=cluster_id
                    )
            else:
                num_to_remove = num_available - desired_count

                for idx in range(num_to_remove):

                    # get the AZ with the most replicas
                    az_with_max = max(reader_az_cnt.items(), key=operator.itemgetter(1))[0]
                    LOGGER.info(f"Removing read replica from AZ {az_with_max}, which has {reader_az_cnt[az_with_max]} replicas")

                    # get one of the replicas from that AZ
                    reader_list = reader_az_map[az_with_max]
                    reader_to_delete = reader_list[0]
                    LOGGER.info(f"Removing read replica {reader_to_delete}")
                    docdb.delete_db_instance(DBInstanceIdentifier=reader_to_delete)

                    reader_az_map[az_with_max].remove(reader_to_delete)
                    reader_az_cnt[az_with_max] -= 1

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
