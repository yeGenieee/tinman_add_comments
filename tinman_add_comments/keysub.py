#!/usr/bin/env python3

from . import util

import argparse
import hashlib
import json
import subprocess
import sys

def process_esc(s, esc="", resolver=None): # esc없는 json_line & esc 문자
    result = []
    for e, is_escaped in util.tag_escape_sequences(s, esc):
        if not is_escaped: # 문자열 e가 esc에 둘러싸인게 아니라면
            result.append(e) # 그냥 바로 file에 작성하도록 붙임
            continue
        ktype, seed = e.split(":", 1) # publickey:owner-init-0 에서 :를 기준으로 자름
        if ktype == "publickey":
            result.append( json.dumps(resolver.get_pubkey(seed))[1:-1] )
        elif ktype == "privatekey":
            result.append( json.dumps(resolver.get_privkey(seed))[1:-1] )
        else:
            raise RuntimeError("invalid input")
    return "".join(result) # join함수 : 리스트에서 문자열로 변환

def compute_keypair_from_seed(seed, get_dev_key_exe="get_dev_key"): # seed는 owner-init-0
    print("@@@compute_keypair_from_seed",end="  ")
    print(seed)
    result_bytes = subprocess.check_output([get_dev_key_exe, "", seed])
    # print(result_bytes,end=" , ")
    result_str = result_bytes.decode("utf-8")
    # print(result_str,end=" , ")
    result_json = json.loads(result_str.strip())
    print(result_json)
    return (result_json[0]["public_key"], result_json[0]["private_key"])

class ProceduralKeyResolver(object):
    """
    Every synthetic testnet key is generated by concatenating the name, secret and role.
    This class is the central place these are issued, and keeps track of all of them.
    """
    #
    def __init__(self, secret="", keyprefix="TST", get_dev_key_exe=""):
        self.seed2pair = {}
        self.secret = secret # secret이 xyz-로 설정됨
        self.keyprefix = keyprefix
        self.get_dev_key_exe = get_dev_key_exe
        # print("@@@2ProceduralKey")
        return

    def get(self, seed=""):
        pair = self.seed2pair.get(seed)
        print("@@pair는? ",end=" ")
        print(pair)
        if pair is None: # pair 가 없는 경우 - 없어서 무조건 들어감!!
            print("@@pair is None")
            pair = compute_keypair_from_seed(self.secret+seed, get_dev_key_exe=self.get_dev_key_exe)
            print("@@만들어진 pair ",end='')
            print(pair)
            self.seed2pair[seed] = pair
        return pair

    def get_pubkey(self, seed):
        return self.get(seed)[0]

    def get_privkey(self, seed):
        return self.get(seed)[1]

def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0], description="Resolve procedural keys") # procedual key를 해결
    parser.add_argument("-i", "--input-file", default="-", dest="input_file", metavar="FILE", help="File to read actions from") # input file
    parser.add_argument("-o", "--output-file", default="-", dest="output_file", metavar="FILE", help="File to write actions to") # output file
    parser.add_argument("--get-dev-key", default="get_dev_key", dest="get_dev_key_exe", metavar="FILE", help="Specify path to get_dev_key tool") # get_dev_key 파일에 대해 특정 경로 지정
    args = parser.parse_args(argv[1:])
    # print("args.input_file = "+str(args.input_file))

    if args.output_file == "-":
        output_file = sys.stdout
    else:
        output_file = open(args.output_file, "w")

    if args.input_file == "-":
        input_file = sys.stdin
    else:
        input_file = open(args.input_file, "r")

    print("@@@1 "+args.get_dev_key_exe)
    # sys.stdout.flush()
    resolver = ProceduralKeyResolver(get_dev_key_exe=args.get_dev_key_exe)
    # print("@@@3resolver")

    for line in input_file:
        line = line.strip()
        # print("input file : line = \n"+line)
        act, act_args = json.loads(line)
        # print(act, end=' , ')
        # print(act_args)

        if act == "set_secret": # echo의 결과로 맨 처음 줄에 set_secret 추가됨
            resolver.secret = act_args["secret"] # xyz- 로 설정
            # print("set_secret : "+str(act)+" , "+str(resolver.secret))
            continue
        esc = act_args.get("esc") # 각 pub, prvKey에 포함된 esc를 가져옴
        if esc:
            # print("@@esc : "+str(esc))
            # print("@@act_args : "+str(act_args))
            act_args_minus_esc = dict(act_args) # dict에 act_args를 모두 저장
            del act_args_minus_esc["esc"] # esc를 dict에서 지움
            json_line_minus_esc = json.dumps([act, act_args_minus_esc], separators=(",", ":"), sort_keys=True) # esc가 빠진 json_line
            line = process_esc(json_line_minus_esc, esc=esc, resolver=resolver)
        output_file.write(line)
        output_file.write("\n")
        output_file.flush()
    if args.input_file != "-":
        input_file.close()
    if args.output_file != "-":
        output_file.close()

if __name__ == "__main__":
    main(sys.argv)
