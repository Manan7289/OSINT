# ALGORITHM_IMPLEMENTATION_GUIDE.md — Exact Mathematical Formulas & Reference Python Implementations

## 1. Jøsang Subjective Logic Belief Fusion & Dong Copying Discount (`M06`)

### 1.1 Mapping NATO Admiralty Ratings to Initial Subjective Logic Opinions
An opinion $\omega_x^S = (b, d, u, a)$ satisfies $b + d + u = 1.0$ with prior base rate $a = 0.5$:
```python
ADMIRALTY_TO_OPINION = {
    # (belief b, disbelief d, uncertainty u)
    "A1": (0.92, 0.00, 0.08),
    "A2": (0.85, 0.02, 0.13),
    "B1": (0.82, 0.02, 0.16),
    "B2": (0.75, 0.05, 0.20),
    "C2": (0.62, 0.08, 0.30),
    "C3": (0.52, 0.12, 0.36),
    "D4": (0.30, 0.25, 0.45),
    "E5": (0.10, 0.55, 0.35),
    "F6": (0.15, 0.15, 0.70),
}
```
If evidence $e$ has `stance == "CONTRADICTS"`, swap $b$ and $d$: $(d, b, u)$.

### 1.2 Averaging Fusion ($\tilde{\oplus}$) Within the Same `upstream_lineage_family` (Echo-Chamber Prevention)
When sources $1, \dots, m$ share the same `upstream_lineage_family` or have 64-bit SimHash Hamming distance $\le 6$, combine them using **Averaging Fusion** so repeating the same upstream report does *not* artificially drive uncertainty $u \to 0$:
```python
def averaging_fusion(opinions: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if not opinions:
        return (0.0, 0.0, 1.0)
    if len(opinions) == 1:
        return opinions[0]
    b_cur, d_cur, u_cur = opinions[0]
    for b_nxt, d_nxt, u_nxt in opinions[1:]:
        denom = max(1e-6, u_cur + u_nxt)
        b_new = (b_cur * u_nxt + b_nxt * u_cur) / denom
        d_new = (d_cur * u_nxt + d_nxt * u_cur) / denom
        u_new = (2.0 * u_cur * u_nxt) / denom
        s = b_new + d_new + u_new
        b_cur, d_cur, u_cur = b_new / s, d_new / s, u_new / s
    return (round(b_cur, 4), round(d_cur, 4), round(u_cur, 4))
```

### 1.3 Cumulative Fusion ($\oplus$) Across Truly Independent Lineage Families
Once each lineage family $F_k$ is reduced to a single representative opinion $\omega_{F_k}$, fuse across distinct families $F_1, \dots, F_K$ using **Cumulative Fusion**:
```python
def cumulative_fusion(opinions: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if not opinions:
        return (0.0, 0.0, 1.0)
    b_cur, d_cur, u_cur = opinions[0]
    for b_nxt, d_nxt, u_nxt in opinions[1:]:
        u_cur = max(1e-4, u_cur)
        u_nxt = max(1e-4, u_nxt)
        denom = u_cur + u_nxt - u_cur * u_nxt
        b_new = (b_cur * u_nxt + b_nxt * u_cur) / denom
        d_new = (d_cur * u_nxt + d_nxt * u_cur) / denom
        u_new = (u_cur * u_nxt) / denom
        s = b_new + d_new + u_new
        b_cur, d_cur, u_cur = b_new / s, d_new / s, u_new / s
    return (round(b_cur, 4), round(d_cur, 4), round(u_cur, 4))
```

---

## 2. 3-Pass Blocking & Unsupervised Fellegi-Sunter EM (`M05`)

### 2.1 Three-Pass Candidate Generation ($O(N \log N)$)
1. **Pass 1 (`PHONETIC_SORT`):** Strip corporate suffixes (`inc`, `llc`, `ltd`, `corp`, `gmbh`, `plc`), compute Soundex/alphanumeric prefix + normalized string, sort lexicographically, and slide window $w = 15$.
2. **Pass 2 (`APEX_PREFIX`):** Group entities sharing the exact apex domain (`example.com`), `/24` IPv4 prefix (`185.220.101.0/24`), ASN (`AS13335`), or LEI code.
3. **Pass 3 (`MINHASH_LSH`):** Compute 12 deterministic 32-bit CRC/MD5 hashes over character 3-grams, partition into $b = 4$ bands of $r = 3$ rows, and emit candidate pairs colliding in any band.

### 2.2 Expectation-Maximization (EM) Parameter Estimation & IEF Adjustment
Given candidate pairs $i \in \{1, \dots, M\}$ and binary comparison agreement indicators $\gamma_{i,k} \in \{0, 1\}$ across features $k \in \{\text{name\_jw}, \text{token\_jaccard}, \text{apex\_domain}, \text{shared\_attr}\}$:
```python
def run_fellegi_sunter_em(gamma_matrix, max_iter: int = 15) -> tuple[float, list[float], list[float], list[float]]:
    # gamma_matrix shape: (M_pairs, K_features) with values in [0.0, 1.0]
    import numpy as np
    M, K = gamma_matrix.shape
    if M == 0:
        return 0.1, [0.9]*K, [0.1]*K, []
    lam = 0.15  # prior match prevalence
    m = np.full(K, 0.88, dtype=np.float64)
    u = np.full(K, 0.12, dtype=np.float64)

    for _ in range(max_iter):
        # E-step: compute posterior match probability p_i for each pair
        log_bf = gamma_matrix * np.log2(np.clip(m / u, 1e-4, 1e4)) + (1.0 - gamma_matrix) * np.log2(np.clip((1.0 - m) / (1.0 - u), 1e-4, 1e4))
        total_log2_w = np.sum(log_bf, axis=1)
        odds = (lam / max(1e-4, 1.0 - lam)) * (2.0 ** np.clip(total_log2_w, -30, 30))
        p = odds / (1.0 + odds)

        # M-step: update m, u, and prevalence lambda
        p_sum = max(1e-6, np.sum(p))
        q_sum = max(1e-6, np.sum(1.0 - p))
        m = np.clip(np.sum(p[:, None] * gamma_matrix, axis=0) / p_sum, 0.55, 0.995)
        u = np.clip(np.sum((1.0 - p[:, None]) * gamma_matrix, axis=0) / q_sum, 0.005, 0.45)
        lam = float(np.clip(np.mean(p), 0.02, 0.50))

    return lam, m.tolist(), u.tolist(), p.tolist()
```

---

## 3. IEF-Weighted Personalized PageRank, Leiden & Adamic-Adar (`M07`)

### 3.1 Inverse Entity Frequency (IEF) Super-Node Dampening
For every edge $e = (u, v)$, compute effective edge weight:
$$w_{\text{eff}}(u, v) = \text{projected\_prob}(e) \cdot \ln\left(1 + \frac{|V|}{\max(1, \text{deg}(v))}\right) \cdot \begin{cases} 0.15 & \text{if } v.\text{is\_shared\_infra} = 1 \\ 1.0 & \text{otherwise} \end{cases}$$

### 3.2 Reciprocal Rank Fusion (`M08`)
Given ranked list $R_{\text{BM25}}$ from SQLite FTS5 `bm25()` and ranked list $R_{\text{vec}}$ from INT8 cosine similarity:
$$\text{RRF\_Score}(d) = \frac{1}{60 + \text{rank}_{\text{BM25}}(d)} + \frac{1}{60 + \text{rank}_{\text{vec}}(d)}$$
