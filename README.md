# bibmerge – Merge and deduplicate multiple BibTeX databases

I was looking for a way to quickly merge all my individual BibTeX databases (.bib files) from my papers.
I wanted to include all my written papers without changes to the cited bibliography keys into a single document, my cumulative dissertation.
The problem is: how do you fix **duplicates of the same bibliography item under different keys**?
That is why I wrote `bibmerge`. It does just that:

- merge the content of multiple BibTeX databases into a single database
- detect duplicate entries with
  - the same BibTeX key (easy)
  - different keys but the same DOI or ISBN,
  - different keys but identical author and title values.
- keep the duplicate BibTeX keys citable by setting them as aliases in the `IDS` field

Then, instead of including all individual BibTeX databases into your document,
you just use the merged database and all your previous cites still work without duplicate entries in your references!

## Installation

bibmerge is available on PyPI:

```
python3 -m pip install bibmerge
```

## Usage

```
bibmerge paper1.bib paper2.bib paper3.bib merged.bib
```
