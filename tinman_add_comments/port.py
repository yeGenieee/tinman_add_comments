#!/usr/bin/env python3

import argparse
import json
import sys
import time

from . import prockey
from . import util
from . import simple_steem_client

def str2bool(str_arg):
    """
    Returns boolean True/False if recognized in string argument, None otherwise.
    """
    return True if str_arg.lower() == 'true' else (False if str_arg.lower() == 'false' else None)

def repack_operations(conf, keydb):
    """
    Uses configuration file data to acquire operations from source node
    blocks/transactions and repack them in new transactions one to one.
    """
    source_node = conf["transaction_source"]["node"]
    is_appbase = str2bool(conf["transaction_source"]["appbase"])
    backend = simple_steem_client.simple_steem_client.client.SteemRemoteBackend(nodes=[source_node], appbase=is_appbase)
    steemd = simple_steem_client.simple_steem_client.client.SteemInterface(backend)
    min_block = int(conf["min_block_number"])
    max_block = int(conf["max_block_number"])
    ported_operations = set(conf["ported_operations"])
    tx_signer = conf["transaction_signer"]
    """ Positive value of max_block means get from [min_block_number,max_block_number) range and stop """
    if max_block > 0: 
        for op in util.iterate_operations_from(steemd, is_appbase, min_block, max_block, ported_operations):
            yield {"operations" : [op], "wif_sigs" : [keydb.get_privkey(tx_signer)]}
        return
    """
    Otherwise get blocks from min_block_number to current head and again
    until you have to wait for another block to be produced (chase-then-listen mode)
    """
    old_head_block = min_block
    while True:
        dgpo = steemd.database_api.get_dynamic_global_properties()
        new_head_block = dgpo["head_block_number"]
        while old_head_block == new_head_block:
            time.sleep(1) # Theoretically 3 seconds, but most probably we won't have to wait that long.
            dgpo = steemd.database_api.get_dynamic_global_properties()
            new_head_block = dgpo["head_block_number"]
        for op in util.iterate_operations_from(steemd, is_appbase, old_head_block, new_head_block, ported_operations):
            yield {"operations" : [op], "wif_sigs" : [keydb.get_privkey(tx_signer)]}
        old_head_block = new_head_block
    return

def build_actions(conf):
    """
    Packs transactions rebuilt with operations acquired from source node into blocks of configured size.
    """
    keydb = prockey.ProceduralKeyDatabase()
    for b in util.batch(repack_operations(conf, keydb), conf["transactions_per_block"]):
        yield ["wait_blocks", {"count" : 1}]
        for tx in b:
            yield ["submit_transaction", {"tx" : tx}]
    yield ["wait_blocks", {"count" : 50}]
    return

def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0], description="Port transactions for Steem testnet")
    parser.add_argument("-c", "--conffile", default="", dest="conffile", metavar="FILE", help="Specify configuration file")
    parser.add_argument("-o", "--outfile", default="-", dest="outfile", metavar="FILE", help="Specify output file, - means stdout")
    args = parser.parse_args(argv[1:])

    with open(args.conffile, "r") as f:
        conf = json.load(f)

    if args.outfile == "-":
        outfile = sys.stdout
    else:
        outfile = open(args.outfile, "w")

    for action in build_actions(conf):
        outfile.write(util.action_to_str(action))
        outfile.write("\n")

    outfile.flush()
    if args.outfile != "-":
        outfile.close()

if __name__ == "__main__":
    main(sys.argv)
