#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module allows to dump snapshot of Main Steem net contents described in the issue:
https://github.com/steemit/tinman/issues/16
"""

import argparse
import json
import sys
from tinman.simple_steem_client.simple_steem_client.client import SteemRemoteBackend, SteemInterface

DATABASE_API_SINGLE_QUERY_LIMIT = 1000 # 쿼리 날려서 가져올 수 있는 결과 최대 개수

# 메인 스팀넷에 존재하는 계정을 가져와서 생성해주는 함수
def list_all_accounts(steemd):
    """ Generator function providing set of accounts existing in the Main Steem net """
    start = ""
    last = ""
    while True:
        result = steemd.database_api.list_accounts( # 계좌의 리스트를 쭉 가져옴
            start=start,
            limit=DATABASE_API_SINGLE_QUERY_LIMIT,
            order="by_name",
            )
        making_progress = False
        for a in result["accounts"]:
            if a["name"] > last:
                yield a # initminer부터 시작
                last = a["name"]
                making_progress = True
            start = last # 마지막에는 temp로 끝남
        if not making_progress:
            break

def list_all_witnesses(steemd):
    """ Generator function providing set of witnesses defined in the Main Steem net """
    # 스팀 메인 넷에 정의된 증인 생성하는 함수
    start = ""
    last = ""
    w_owner = ""

    while True:
        result = steemd.database_api.list_witnesses(
            start=start,
            limit=DATABASE_API_SINGLE_QUERY_LIMIT,
            order="by_name",
            )
        making_progress = False
        for w in result["witnesses"]:
            w_owner = w["owner"]
            if w_owner > last:
                yield w_owner # Only `owner` member shall be provided
                last = w_owner
                making_progress = True
            start = last
        if not making_progress:
            break

# Helper function to reuse code related to collection dump across different usecases
# json dump를 위한 함수
def dump_collection(c, outfile):
    """ Allows to dump collection into JSON string. """
    outfile.write("[\n")
    first = True
    for o in c:
        if not first:
            outfile.write(",\n")
        json.dump( o, outfile, separators=(",", ":"), sort_keys=True )
        first = False
    outfile.write("\n]")

def dump_all_accounts(steemd, outfile):
    """ Allows to dump into the snapshot all accounts provided by Steem Net"""
    # 스팀 메인 넷에서 제공 되는 모든 계정의 스냅샷을 dump하는 것 허용
    dump_collection(list_all_accounts(steemd), outfile)

def dump_all_witnesses(steemd, outfile):
    """ Allows to dump into the snapshot all witnesses provided by Steem Net"""
    # 스팀 메인 넷에서 제공 되는 모든 증인을 dump
    dump_collection(list_all_witnesses(steemd), outfile)

def dump_dgpo(steemd, outfile):
    """ Allows to dump into the snapshot all Dynamic Global Properties Objects
        provided by Steem Net
        모든 dgpo를 스냅샷에 dump
    """
    dgpo = steemd.database_api.get_dynamic_global_properties(x=None) # database_api 호출
    json.dump( dgpo, outfile, separators=(",", ":"), sort_keys=True ) # 출력파일에 api call했던 내용 적음 - sort_keys=True이므로 key로 정렬

def main(argv): # snapshot.py의 메인
    """ Tool entry point function """
    parser = argparse.ArgumentParser(prog=argv[0], description="Create snapshot files for Steem") # Steem을 위한 스냅샷찍기
    parser.add_argument("-s", "--server", default="http://127.0.0.1:8090", dest="server", metavar="URL", help="Specify mainnet steemd server") # -s 는 --server 호출하는 명령어
    parser.add_argument("-o", "--outfile", default="-", dest="outfile", metavar="FILE", help="Specify output file, - means stdout") # -o : 출력파일지정
    args = parser.parse_args(argv[1:])

    if args.outfile == "-":
        outfile = sys.stdout
    else:
        outfile = open(args.outfile, "w")

    backend = SteemRemoteBackend(nodes=[args.server], appbase=True) # appbase 버전인 경우 - rpc 호출하도록 SteemRemoteBackend 클래스 호출
    steemd = SteemInterface(backend) # steemd 설정을 위해 SteemInterface 클래스 호출

    # 출력파일에 작성 (snapshot.json)
    outfile.write("{\n")
    outfile.write('"dynamic_global_properties":')
    dump_dgpo(steemd, outfile)
    outfile.write(',\n"accounts":')
    dump_all_accounts(steemd, outfile)
    outfile.write(',\n"witnesses":')
    dump_all_witnesses(steemd, outfile)
    outfile.write("\n}\n")
    outfile.flush()
    if args.outfile != "-":
        outfile.close()
    return

if __name__ == "__main__":
    main(sys.argv)
