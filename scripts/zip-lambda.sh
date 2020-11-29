#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

bucket=$1
prefix="functions"

if [ "$bucket" == "" ]
then
    echo "Usage: $0 <bucket>"
    exit 1
fi

cd lambda
rm -f lambda-get.zip
rm -f lambda-patch.zip
zip lambda-get.zip index_get.py
zip lambda-patch.zip index_patch.py
aws s3 cp lambda-get.zip s3://$bucket/$prefix/lambda-get.zip
aws s3 cp lambda-patch.zip s3://$bucket/$prefix/lambda-patch.zip
cd ..

sleep 5
aws s3api list-object-versions --bucket $bucket --prefix $prefix/lambda-get.zip | jq -r '.Versions | .[] | {IsLatest, VersionId} | select(.IsLatest==true) | {VersionId} | to_entries[] |"\(.value)" ' > latest_get.txt
aws s3api list-object-versions --bucket $bucket --prefix $prefix/lambda-patch.zip | jq -r '.Versions | .[] | {IsLatest, VersionId} | select(.IsLatest==true) | {VersionId} | to_entries[] |"\(.value)" ' > latest_patch.txt
