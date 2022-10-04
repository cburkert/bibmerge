import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import io
import logging
import os
import re
from typing import *

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase


logging.basicConfig()
logger = logging.getLogger("bibmerge")


BibEntry_T = Dict[str, str]


@dataclass
class BibFile:
    name: str
    mtime: datetime
    entries: Dict[str, BibEntry_T]

    @property
    def keys(self):
        return list(self.entries.keys())


class BibMerger:
    def __init__(self):
        self.bibs: List[BibFile] = []

    def add_bib(self, bibfile: TextIO):
        bib = parse_bibfile(bibfile)
        self.bibs.append(bib)

    def print_info(self):
        print(f"Bibs: {len(self.bibs)}")
        for bib in self.bibs:
            print(f"- {bib.name} {len(bib.entries)} entries")

    def merge(self, out: TextIO):
        merged: Dict[str, BibEntry_T] = {}
        mtimes: Dict[str, datetime] = {}
        aliases: Dict[str, Set[str]] = defaultdict(set)
        alias_map: Dict[str, str] = {}

        # iterate over bibs and add new
        # or replace existing if newer
        for bib in self.bibs:
            for key, entry in bib.entries.items():
                if key in merged or key in alias_map:
                    logger.debug("Duplicate key %s", key)
                    refkey = alias_map.get(key, key)
                    ext_mtime = mtimes[refkey]
                    if ext_mtime < bib.mtime:
                        # use new entry
                        entry["ID"] = refkey
                        merged[refkey] = entry
                        mtimes[refkey] = bib.mtime
                else:
                    # check for entry under different keys
                    if ext_key := self._match(key, entry, merged):
                        # we found a matching entry
                        # add new key to aliases of existing keys
                        aliases[ext_key].add(key)
                        assert key not in alias_map, key
                        alias_map[key] = ext_key
                        # use new entry if newer
                        ext_mtime = mtimes[ext_key]
                        if ext_mtime < bib.mtime:
                            # update but keep old key (here ID)
                            entry["ID"] = ext_key
                            merged[ext_key] = entry
                            mtimes[ext_key] = bib.mtime
                    else:
                        # no matching entry found - safe to add
                        merged[key] = entry
                        mtimes[key] = bib.mtime

        # put alias info into IDS field
        for key, ids in aliases.items():
            prev_ids = merged[key].get("ids")
            assert not prev_ids, key
            assert key not in ids, ids
            assert merged[key]["ID"] == key, key
            merged[key]["ids"] = ",".join(ids)

        outdb = BibDatabase()
        outdb.entries = list(merged.values())
        with out:
            bibtexparser.dump(outdb, out)


    def _match(self, nkey: str, nentry: BibEntry_T,
               merged: Dict[str, BibEntry_T]) -> Optional[str]:
        matching = [
            (okey, oentry)
            for okey, oentry in merged.items()
            if self._compare(nkey, nentry, okey, oentry)
        ]
        assert len(matching) <= 1, matching
        if matching:
            return matching[0][0]
        return None


    def _compare(self, nkey: str, nentry: BibEntry_T,
                 okey: str, oentry: BibEntry_T) -> bool:
        assert nkey != okey
        oauthor = oentry.get("author", "")
        nauthor = nentry.get("author", "")
        otitle = oentry.get("title", "")
        ntitle = nentry.get("title", "")
        # check for clear identifiers
        for field in ["doi"]:
            oval = oentry.get(field)
            nval = nentry.get(field)
            if oval == nval and oval is not None:
                # double check with title to avoid false matches due
                # to bad data
                if not str_compare(otitle, ntitle):
                    logger.warning("Skipping dubious %s match for %s and %s",
                                   field, okey, nkey)
                    return False
                logger.info("Found match between %s and %s based on %s",
                            okey, nkey, field)
                return True
        # check for identical author and title
        if (oauthor == nauthor and oauthor and otitle == ntitle and otitle):
            logger.info("Found match between %s and %s based on author/title",
                        okey, nkey)
            return True
        return False


def str_compare(valA: str, valB: str) -> bool:
    return stripped(valA) == stripped(valB)


def stripped(val: str) -> str:
    val = val.replace("{", "").replace("}", "")
    val = val.replace("\n", "").replace("\r", "")
    val = val.lower()
    val = re.sub(r"\s* ", " ", val)
    val = val.strip()
    return val


def parse_bibfile(bibfile: TextIO) -> BibFile:
    mtime = datetime.fromtimestamp(os.path.getmtime(bibfile.fileno()))
    with bibfile:
        stripped = strip_commented_lines(bibfile)
    parser = BibTexParser()
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = False
    parser.common_strings = False
    entries = bibtexparser.load(stripped, parser)
    assert len(entries.entries) == len(entries.entries_dict)
    return BibFile(
        bibfile.name,
        mtime,
        entries.entries_dict,
    )


def strip_commented_lines(bibfile: TextIO) -> TextIO:
    """Workaround for bibtexparser's bug misclassifying entries with commented
    out lines ('%') as ImplicitComment"""
    lines = bibfile.readlines()
    stripped = [
        line
        for line in lines
        if not re.match(r"\s*%", line)
    ]
    return io.StringIO("\n".join(stripped))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bibfiles", type=argparse.FileType("r"), nargs="+",
                        help=".bib file")
    parser.add_argument("mergedbib", type=argparse.FileType("w"),
                        help="Output .bib file for merged entries")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Debug output")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)
    fns = args.bibfiles
    merger = BibMerger()
    for bibfn in fns:
        merger.add_bib(bibfn)
    if args.verbose or args.debug:
        merger.print_info()
    merger.merge(args.mergedbib)


if __name__ == "__main__":
    main()
