# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import sys

if len(sys.argv) < 5:
    print("Usage: register.py <ApiEndpoint> <Region> <DBClusterIdentifier> <AWS Account>")
    sys.exit(1)
ApiEndpoint = sys.argv[1]
Region = sys.argv[2] 
DBClusterIdentifier = sys.argv[3] 
Account = sys.argv[4]

client = boto3.client('application-autoscaling')
response = client.register_scalable_target(
    ServiceNamespace='custom-resource',
    ResourceId='https://' + ApiEndpoint + '.execute-api.' + Region + '.amazonaws.com/prod/scalableTargetDimensions/' + DBClusterIdentifier, 
    ScalableDimension='custom-resource:ResourceType:Property', 
    MinCapacity=2, 
    MaxCapacity=15, 
    RoleARN='arn:aws:iam::' + Account + ':role/aws-service-role/custom-resource.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_CustomResource'
)

response = client.put_scaling_policy(
    PolicyName='docdbscalingpolicy',
    ServiceNamespace='custom-resource',
    ResourceId='https://' + ApiEndpoint + '.execute-api.' + Region + '.amazonaws.com/prod/scalableTargetDimensions/' + DBClusterIdentifier, 
    ScalableDimension='custom-resource:ResourceType:Property', 
    PolicyType='TargetTrackingScaling',
    TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 5.0,
        'CustomizedMetricSpecification': {
            'MetricName': 'CPUUtilization',
            'Namespace': 'AWS/DocDB',
            'Dimensions': [
                {
                    'Name': 'Role',
                    'Value': 'READER'
                },
                {
                    'Name': 'DBClusterIdentifier',
                    'Value': DBClusterIdentifier
                }
            ],
            'Statistic': 'Average',
            'Unit': 'Percent'
        },
        'ScaleOutCooldown': 600,
        'ScaleInCooldown': 600,
        'DisableScaleIn': False
    }
)
