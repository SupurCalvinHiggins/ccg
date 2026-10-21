# ccg

A (vibe-coded) tool to visualize code co-occurence graphs.

## Overview

If you want to understand your codebook's global structure and you have:
1. Dozens of coded interview transcripts
1. Thousands of coded quotes
1. Hundreds of codes
code co-occurence graphs (CCGs) may help.

In codebooks, transitive relationships like `A~B` and `B~C` so `A~C` are implict. Although code `A`'s description may mention code `B`, and code `B`'s description may mention code `C`, noticing the relationship between `A` and `C` through `B` requires additional effort. With large datasets, manually identifying higher-order relationships becomes intractable: if $$n$$ is the codebook size, the number of potential relationships is $$2^n$$. Even the number of potential second-order relationships -- $\frac{n^2}{2} - \frac{n}{2}$$ -- quickly becomes infeasible. CCGs solve this problem by visualizing "reasonable" higher-order relationships between codes. Researchers can then analyze this smaller set of candidate relationships.

## Installation

Do the following:
1. Install `uv`.
1. Install `git`.
1. Clone the repository with `git`.
1. Run `uv sync` in the repository root.

## Usage

Do the following:
1. Export your codebook as a CSV file in this format:
```csv
participant,codes
<name>,<code1>|<code2>|...|<codeN>
```
1. From the repository root, run `uv run -m qualgraph.server --port 8080` to start the server.
1. Open `http://localhost:8080` in a web browser.
1. Upload your codebook CSV. **Your data will remain on your device. Your data will NOT be sent over the internet.**
