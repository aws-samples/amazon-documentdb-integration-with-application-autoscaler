#!/usr/bin/env bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

templatebucket=$1
templateprefix=$2
dbpassword=$3
stackname=$4
region=$5
SCRIPTDIR=`dirname $0`
if [ "$templatebucket" == "" ]
then
    echo "Usage: $0 <template bucket> <template prefix> <database password> <stack name> <region>"
    exit 1
fi
if [ "$templateprefix" == "" ]
then
    echo "Usage: $0 <template bucket> <template prefix> <database password> <stack name> <region>"
    exit 1
fi
if [ "$dbpassword" == "" ]
then
    echo "Usage: $0 <template bucket> <template prefix> <database password> <stack name> <region>"
    exit 1
fi
if [ "$stackname" == "" ]
then
    echo "Usage: $0 <template bucket> <template prefix> <database password> <stack name> <region>"
    exit 1
fi
if [ "$region" == "" ]
then
    echo "Usage: $0 <template bucket> <template prefix> <database password> <stack name> <region>"
    exit 1
fi
UPDATE=${6:-""}
CFN_CMD="create-stack"
if [ "$UPDATE" == "--update" ]
then
    CFN_CMD="update-stack"
    echo "Updating stack"
fi

# Check if we need to append region to S3 URL
TEMPLATE_URL=https://s3.amazonaws.com/$templatebucket/$templateprefix/main.yaml
if [ "$region" != "us-east-1" ]
then
    TEMPLATE_URL=https://s3-$region.amazonaws.com/$templatebucket/$templateprefix/main.yaml
fi

aws s3 sync $SCRIPTDIR/../cfn s3://$templatebucket/$templateprefix

echo "Reading object version of lambda zips"
LAMBDA_ZIP_GET=`cat latest_get.txt`
LAMBDA_ZIP_PATCH=`cat latest_patch.txt`

aws cloudformation $CFN_CMD --stack-name $stackname \
    --template-url $TEMPLATE_URL \
    --parameters \
    ParameterKey=TemplateBucketName,ParameterValue=$templatebucket \
    ParameterKey=TemplateBucketPrefix,ParameterValue=$templateprefix \
    ParameterKey=PrimaryPassword,ParameterValue=$dbpassword \
    ParameterKey=ZipGet,ParameterValue=$LAMBDA_ZIP_GET \
    ParameterKey=ZipPatch,ParameterValue=$LAMBDA_ZIP_PATCH \
    --tags Key=Project,Value=DocDbLambda \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
