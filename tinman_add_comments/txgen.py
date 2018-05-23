#!/usr/bin/env python3

import argparse
import datetime
import hashlib
import itertools
import json
import os
import random
import sys

from . import prockey
from . import util

STEEM_GENESIS_TIMESTAMP = 1451606400
STEEM_BLOCK_INTERVAL = 3


# 계정 생성 하는 함수
def create_accounts(conf, keydb, name):
    desc = conf["accounts"][name] # txgen.conf의 accounts 이름 가져옴
    # print("@@ desc.get('count')"+str(desc.get("count")))
    for index in range(desc.get("count", 1)):
        name = desc["name"].format(index=index) # init-0부터 시작 ~ 20까지, # elect-0 ~ elect-9 # tnman, porter
        yield {"operations" : [["account_create",{
            "fee" : desc["vesting"],
            "creator" : desc["creator"], # conf의 creator
            "new_account_name" : name,
            "owner" : keydb.get_authority(name, "owner"),
            "active" : keydb.get_authority(name, "active"),
            "posting" : keydb.get_authority(name, "posting"),
            "memo_key" : keydb.get_pubkey(name, "memo"),
            "json_metadata" : "",
           }]],
           "wif_sigs" : [keydb.get_privkey(desc["creator"])]} # 지갑 서명은 creator의 private key로
    return

# 투표 계정
def vote_accounts(conf, keydb, elector, elected):
    er_desc = conf["accounts"][elector] # elector
    ed_desc = conf["accounts"][elected] # init

    er_count = er_desc["count"] # 10
    ed_count = ed_desc["count"] # 21

    rr = itertools.cycle(range(ed_count)) # 0~20이 계속 반복되는 리스트

    rand = random.Random(er_desc["randseed"]) # 1234

    for er_index in range(er_desc["count"]):
        votes = []
        for i in range(er_desc["round_robin_votes_per_elector"]): # 2
            votes.append(next(rr))
        for i in range(er_desc["random_votes_per_elector"]): # 3
            votes.append(rand.randrange(0, ed_count))
        votes = sorted(set(votes))
        ops = []
        er_name = er_desc["name"].format(index=er_index)
        for ed_index in votes:
           ed_name = ed_desc["name"].format(index=ed_index)
           ops.append(["account_witness_vote", {
            "account" : er_name,
            "witness" : ed_name,
            "approve" : True,
            }])
        yield {"operations" : ops, "wif_sigs" : [keydb.get_privkey(er_name)]}
    return

# 증인 노드 업데이트
def update_witnesses(conf, keydb, name):
    desc = conf["accounts"][name] # init의 계좌만 뽑아냄
    for index in range(desc["count"]):
        name = desc["name"].format(index=index)
        yield {"operations" : [["witness_update",{
            "owner" : name,
            "url" : "https://steemit.com/",
            "block_signing_key" : "TST6LLegbAgLAy28EHrffBVuANFWcFgmqRMW13wBmTExqFE9SCkg4",
            "props" : {},
            "fee" : amount(0),
           }]],
           "wif_sigs" : [keydb.get_privkey(name)]}
    return

# 트랜잭션 빌드하는 함수 - 계좌 생성
def build_setup_transactions(conf, keydb):
    yield from create_accounts(conf, keydb, "init") # 함수 바깥으로 리스트의 각 요소를 전달
    yield from create_accounts(conf, keydb, "elector")
    yield from create_accounts(conf, keydb, "manager")
    yield from create_accounts(conf, keydb, "porter")
    yield from port_snapshot(conf, keydb)


# initminer의 트랜잭션 build
def build_initminer_tx(conf, keydb): # keydb는 Pubkey Prvkey의 쌍
    return {"operations" : [
     ["account_update",
      {
       "account" : "initminer",
       "owner" : keydb.get_authority("initminer", "owner"), # [["Bpublickey:owner-initminerB",1]]
       "active" : keydb.get_authority("initminer", "active"),
       "posting" : keydb.get_authority("initminer", "posting"),
       "memo_key" : keydb.get_pubkey("initminer", "memo"),
       "json_metadata" : "",
      }],
     ["transfer_to_vesting",
      {
       "from" : "initminer",
       "to" : "initminer",
       "amount" : conf["accounts"]["initminer"]["vesting"], # initminer의 vest값 가져옴
      }],
     ["account_witness_vote",
      {
       "account" : "initminer",
       "witness" : "initminer",
       "approve" : True,
      }],
    ],
    "wif_sigs" : ["5JNHfZYKGaomSFvd4NUdQ9qMcEAC43kujbfjueTHpVapX1Kzq2n"]} # initminer의 wif_sigs 고정

def satoshis(s):
    return int(s[0])

def amount(satoshis, prec=3, symbol="@@000000021"):
    return [str(satoshis), prec, symbol]

# 시스템 계좌 이름을 가져오는 함수
def get_system_account_names(conf):
    for desc in conf["accounts"].values(): # desc는 initminer, init, elector, porter, manager, STEEM_MINER_ACCOUNT, STEEM_NULL_ACCOUNT, STEEM_TEMP_ACCOUNT
        for index in range(desc.get("count", 1)):
            name = desc["name"].format(index=index)
            # print("@@@@In get_system_account_names : "+name)
            yield name
    return

# 스냅샷 이식하는 함수
def port_snapshot(conf, keydb):
    with open(conf["snapshot_file"], "r") as f: # snapshot.json 읽어옴
        snapshot = json.load(f)
        
    # 바꾼 부분(0으로 나누는 문제)
    total_vests = 100
    total_steem = 100

    # total_vests = 0
    # total_steem = 0

    system_account_names = set(get_system_account_names(conf)) # txgen.conf 파일에 있는 시스템 계좌 가져옴
    # print(sorted(system_account_names))

    # 스냅샷에서 시스템 계좌 아닌 사용자 계정을 가지고오는 함수
    def user_accounts():
        # for b in snapshot["accounts"]:
        #     if b["name"] not in system_account_names:
        #         print("system_account_names Not"+b)

        return (a for a in snapshot["accounts"] if a["name"] not in system_account_names)

    num_accounts = 0 # 계좌 개수
    for acc in user_accounts():
        total_vests += satoshis(acc["vesting_shares"]) # TODO vesting_shares가 없음!!!!! - txgen.conf에 추가할 것!
        # print("acc['balance'] : " + acc["balance"])
        total_steem += satoshis(acc["balance"]) # TODO txgen.conf에 balance도 추가 필요
        num_accounts += 1

    # We have a fixed amount of STEEM to give out, specified by total_port_balance
    # This needs to be given out subject to the following constraints:
    # - The ratio of vesting : liquid STEEM is the same on testnet,
    # - Everyone's testnet balance is proportional to their mainnet balance
    # - Everyone has at least min_vesting_per_account

    dgpo = snapshot["dynamic_global_properties"] # snapshot의 dynamic_global_properties
    denom = 10**12        # we need stupidly high precision because VESTS - 지분같은 개념
    min_vesting_per_account = satoshis(conf["min_vesting_per_account"])
    total_vesting_steem = satoshis(dgpo["total_vesting_fund_steem"])
    # print("total_vesting_steem : " + str(total_vesting_steem))
    total_port_balance = satoshis(conf["total_port_balance"]) # 리스트 형태로 들어감
    avail_port_balance = total_port_balance - min_vesting_per_account * num_accounts
    if avail_port_balance < 0:
        raise RuntimeError("Increase total_port_balance or decrease min_vesting_per_account")
    # print("total_steem : "+str(total_steem))
    # print("total_vesting_steem : "+str(total_vesting_steem))
    total_port_vesting = (avail_port_balance * total_vesting_steem) // (total_steem + total_vesting_steem)
    total_port_liquid = (avail_port_balance * total_steem) // (total_steem + total_vesting_steem)
    vest_conversion_factor  = (denom * total_port_vesting) // total_vests
    steem_conversion_factor = (denom * total_port_liquid ) // total_steem

    """
    print("total_vests:", total_vests)
    print("total_steem:", total_steem)
    print("total_vesting_steem:", total_vesting_steem)
    print("total_port_balance:", total_port_balance)
    print("total_port_vesting:", total_port_vesting)
    print("total_port_liquid:", total_port_liquid)
    print("vest_conversion_factor:", vest_conversion_factor)
    print("steem_conversion_factor:", steem_conversion_factor)
    """

    porter = conf["accounts"]["porter"]["name"] # porter

    yield {"operations" : [
      ["transfer",
      {"from" : "initminer",
       "to" : porter,
       "amount" : conf["total_port_balance"], # ["200000000000",3,"@@000000021"]
       "memo" : "Fund porting balances",
      }]],
       "wif_sigs" : [keydb.get_privkey("initminer")]} # initminer의 private key 가져옴

    porter_wif = keydb.get_privkey("porter") # porter의 private key 가져옴

    create_auth = {"account_auths" : [["porter", 1]], "key_auths" : [], "weight_threshold" : 1}

    for a in user_accounts(): # 시스템 계좌 말고 사용자계좌 - 현재 없음
        print("@@user_aaccounts"+str(a["name"]))
        vesting_amount = (satoshis(a["vesting_shares"]) * vest_conversion_factor) // denom
        transfer_amount = (satoshis(a["balance"]) * steem_conversion_factor) // denom
        name = a["name"]
        tnman = conf["accounts"]["manager"]["name"]

        ops = [["account_create",{
          "fee" : amount(max(vesting_amount, min_vesting_per_account)),
          "creator" : porter,
          "new_account_name" : name,
          "owner" : create_auth,
          "active" : create_auth,
          "posting" : create_auth,
          "memo_key" : "TST"+a["memo_key"][3:],
          "json_metadata" : "",
         }]]
        if transfer_amount > 0:
            ops.append(["transfer",{
             "from" : porter,
             "to" : name,
             "amount" : amount(transfer_amount),
             "memo" : "Ported balance",
             }])

        print("@@@@@@여기 들어옴?")

        yield {"operations" : ops, "wif_sigs" : [porter_wif]}

    for a in user_accounts():
        print("@@@@@@여기 들어2222옴?")
        cur_auth = json.loads(json.dumps(a["posting"]))
        non_existing_account_auths = []
        # filter to only include existing accounts
        cur_auth["account_auths"] = [aw for aw in cur_auth["account_auths"] if
           (aw in snapshot["accounts"]) and (aw not in system_account_names)]

        # add tnman to account_auths
        cur_auth["account_auths"].append([tnman, cur_auth["weight_threshold"]])
        # substitute prefix for key_auths
        cur_auth["key_auths"] = [["TST"+k[3:], w] for k, w in cur_auth["key_auths"]]

        ops = [["account_update",{
          "account" : a["name"],
          "owner" : cur_auth,
          "active" : cur_auth,
          "posting" : cur_auth,
          "memo_key" : "TST"+a["memo_key"][3:],
          "json_metadata" : a["json_metadata"],
          }]]

        yield {"operations" : ops, "wif_sigs" : [porter_wif]}

    return

def build_actions(conf): # 명령어 빌드하는 부분
    keydb = prockey.ProceduralKeyDatabase() # keydb는 Pubkey와 Prvkey의 쌍

    start_time = datetime.datetime.strptime(conf["start_time"], "%Y-%m-%dT%H:%M:%S") # 2018-01-24T12:00:00
    genesis_time = datetime.datetime.utcfromtimestamp(STEEM_GENESIS_TIMESTAMP) # STEEM_GENESIS_TIMESTAMP = 1451606400
    miss_blocks = int((start_time - genesis_time).total_seconds()) // STEEM_BLOCK_INTERVAL # 놓친 블록 (만들어진 블록의 개수??)
    miss_blocks = max(miss_blocks-1, 0)

    yield ["wait_blocks", {"count" : 1, "miss_blocks" : miss_blocks}] # yield 만나므로 main함수로 복귀 - 이 줄 그대로 가게 됨
    yield ["submit_transaction", {"tx" : build_initminer_tx(conf, keydb)}] # initminer 트랜잭션 빌드
    for b in util.batch(build_setup_transactions(conf, keydb), conf["transactions_per_block"]): # transactions per block 은 40으로 설정(txgen.conf)
        yield ["wait_blocks", {"count" : 1}]
        for tx in b:
            # print(str(tx["operations"]))
            yield ["submit_transaction", {"tx" : tx}]

    for tx in update_witnesses(conf, keydb, "init"): # 증인 업데이트
        yield ["submit_transaction", {"tx" : tx}]
    for tx in vote_accounts(conf, keydb, "elector", "init"): # 투표 업데이트
        yield ["submit_transaction", {"tx" : tx}]
    yield ["wait_blocks", {"count" : 1000000000}]

    return

# tinman txgen -c ~/src_app /tinman/txgen.conf -o tn.txlist

def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0], description="Generate transactions for Steem testnet") # 스팀 테스트넷을 위해 트랜잭션을 생성
    parser.add_argument("-c", "--conffile", default="", dest="conffile", metavar="FILE", help="Specify configuration file") # configuration file 지정
    parser.add_argument("-o", "--outfile", default="-", dest="outfile", metavar="FILE", help="Specify output file, - means stdout") # 출력파일 지정
    args = parser.parse_args(argv[1:])

    with open(args.conffile, "r") as f:
        conf = json.load(f)

    if args.outfile == "-": # 모니터로 출력
        outfile = sys.stdout
    else: # 출력파일 열기
        outfile = open(args.outfile, "w")

    for action in build_actions(conf):
        outfile.write(util.action_to_str(action))
        outfile.write("\n")

    outfile.flush()
    if args.outfile != "-":
        outfile.close()

if __name__ == "__main__":
    main(sys.argv)
