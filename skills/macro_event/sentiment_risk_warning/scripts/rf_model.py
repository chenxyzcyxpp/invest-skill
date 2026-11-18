# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
rf_model.py — 舆情风险预警 skill 共享模型层
============================================
提供预处理流水线（Winsor 缩尾 → VIF 共线性过滤 → Z-score 标准化）
与随机森林回归模型。scikit-learn 可用时优先使用 sklearn，
缺失时自动回退到等价的 numpy 实现（bootstrap 采样 + 随机特征子集
递归分割 + 叶子均值）。

设计原则（对应 skill 工程约束）：
- 模型输入全部为相对值/比率/分位数，禁止直接喂原始绝对值。
- 严格前向预测：训练只用 t-1 日及以前的特征预测 t 日标签。
- 所有失败场景返回明确异常，禁止伪造预测结果。

命令行用法：本模块为库，供 market_risk.py 与 stock_risk_scorer 导入。
"""

import math
import numpy as np

# ---------------------------------------------------------------------------
# 预处理流水线
# ---------------------------------------------------------------------------

def winsorize(x, limits=(0.025, 0.025)):
    """Winsor 缩尾：把超过上下分位数的极值压缩到分位数处。

    参数
    ----
    x : np.ndarray, shape (n,)
    limits : (low, high) 各端缩尾比例，默认各 2.5%

    返回
    ----
    np.ndarray : 与 x 同形状的缩尾后数组
    """
    x = np.asarray(x, dtype=float)
    low_q = np.quantile(x, limits[0]) if limits[0] > 0 else -np.inf
    high_q = np.quantile(x, 1.0 - limits[1]) if limits[1] > 0 else np.inf
    return np.clip(x, low_q, high_q)


def _vif_for_column(X, j):
    """计算第 j 列对其它列的方差膨胀因子 VIF = 1/(1-R^2)。"""
    n, p = X.shape
    if p <= 1:
        return 1.0
    y = X[:, j]
    cols = [c for c in range(p) if c != j]
    Xj = X[:, cols]
    # 加一列常数项做带截距回归
    A = np.column_stack([np.ones(n), Xj])
    try:
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    except np.linalg.LinAlgError:
        return np.inf
    resid = y - A @ coef
    ss_res = float(resid @ resid)
    ss_tot = float((y - y.mean()) @ (y - y.mean()))
    if ss_tot < 1e-12:
        return np.inf
    r2 = 1.0 - ss_res / ss_tot
    r2 = max(0.0, min(r2, 1.0 - 1e-12))
    return 1.0 / (1.0 - r2)


def vif_filter(X, feature_names, threshold=10.0):
    """VIF 共线性过滤：迭代删除 VIF 最高的特征，直到全部低于阈值。

    参数
    ----
    X : np.ndarray, shape (n, p)
    feature_names : list[str]，与 X 列一一对应
    threshold : float，VIF 阈值，默认 10

    返回
    ----
    kept_idx : list[int]，保留的特征列索引（按原顺序）
    removed : list[str]，被剔除的特征名及原因（供报告输出）
    """
    X = np.asarray(X, dtype=float)
    names = list(feature_names)
    kept_idx = list(range(X.shape[1]))
    removed = []
    while len(kept_idx) > 1:
        Xk = X[:, kept_idx]
        vifs = [_vif_for_column(Xk, j) for j in range(Xk.shape[1])]
        jmax = int(np.argmax(vifs))
        if vifs[jmax] <= threshold:
            break
        removed.append("%s(VIF=%.2f)" % (names[kept_idx[jmax]], vifs[jmax]))
        del kept_idx[jmax]
    return kept_idx, removed


def zscore(X, mu=None, sigma=None):
    """Z-score 标准化。可传入训练期保存的 mu/sigma 用于推理期同口径变换。"""
    X = np.asarray(X, dtype=float)
    if mu is None:
        mu = X.mean(axis=0)
    if sigma is None:
        sigma = X.std(axis=0)
    sigma = np.where(sigma < 1e-12, 1.0, sigma)
    return (X - mu) / sigma, mu, sigma


# ---------------------------------------------------------------------------
# 随机森林回归（sklearn 优先 / numpy 回退）
# ---------------------------------------------------------------------------

def _try_import_sklearn():
    """尝试导入 sklearn 随机森林；失败返回 None。"""
    try:
        from sklearn.ensemble import RandomForestRegressor as SKRF
        return SKRF
    except Exception:
        return None


class _Node:
    """numpy 回退实现的决策树节点（存储型，非对象递归，防深递归栈溢出）。"""

    __slots__ = ("feature", "threshold", "left", "right", "value", "n_samples", "_idx")

    def __init__(self):
        self.feature = None      # 分裂特征索引
        self.threshold = None    # 分裂阈值
        self.left = None         # 左子节点索引
        self.right = None        # 右子节点索引
        self.value = None        # 叶子均值
        self.n_samples = 0


class _NumpyDecisionTree:
    """numpy 实现的回归决策树（CART 方差下降准则，随机特征子集）。"""

    def __init__(self, max_depth=10, min_samples_split=3,
                 min_samples_leaf=2, max_features=None, seed=0):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.seed = seed
        self.nodes = []

    def fit(self, X, y):
        self.nodes = []
        root = _Node()
        self._grow(X, y, root, 0)
        self.nodes.append(root)
        return self

    def _new_node(self):
        node = _Node()
        self.nodes.append(node)
        return len(self.nodes) - 1

    def _best_split(self, X, y, idx, rng):
        """在 idx 样本子集上找最优（feature, threshold）。

        每个节点随机抽取 max_features 个特征子集，只在这些特征上
        搜索最优分裂（方差下降最大），对应随机森林的随机性来源之一。
        """
        n = len(idx)
        if n < self.min_samples_split:
            return None, None
        p = X.shape[1]
        mtry = self.max_features if self.max_features is not None else max(1, int(math.sqrt(p)))
        feats = rng.choice(p, size=min(mtry, p), replace=False)
        y_sub = y[idx]
        parent_var = float(np.var(y_sub))
        if parent_var < 1e-15:
            return None, None
        best_gain, best_f, best_t = -1.0, None, None
        for f in feats:
            vals = X[idx, f]
            order = np.argsort(vals, kind="mergesort")
            v_sorted = vals[order]
            # 只需在相邻不同值的中点尝试，避免重复阈值
            uniq = np.unique(v_sorted)
            if uniq.shape[0] < 2:
                continue
            cand = (uniq[:-1] + uniq[1:]) / 2.0
            y_sorted = y_sub[order]
            # 前缀和加速方差计算
            cs = np.cumsum(y_sorted)
            cs2 = np.cumsum(y_sorted * y_sorted)
            left_pos = np.searchsorted(v_sorted, cand, side="right")
            for t, ln in zip(cand, left_pos):
                if ln < self.min_samples_leaf or (n - ln) < self.min_samples_leaf:
                    continue
                s_left = cs[ln - 1] if ln > 0 else 0.0
                s2_left = cs2[ln - 1] if ln > 0 else 0.0
                s_right = cs[-1] - s_left
                s2_right = cs2[-1] - s2_left
                var_l = s2_left / ln - (s_left / ln) ** 2
                var_r = s2_right / (n - ln) - (s_right / (n - ln)) ** 2
                gain = parent_var - (ln / n) * var_l - ((n - ln) / n) * var_r
                if gain > best_gain:
                    best_gain, best_f, best_t = gain, int(f), float(t)
        return best_f, best_t

    def _grow(self, X, y, node, depth):
        """递归生长节点。返回值写回 node 的索引引用，父节点持有子节点索引。"""
        idx = node._tmp_idx if hasattr(node, "_tmp_idx") else None
        # 简化：直接使用 node 上的样本索引列表（在 fit 中维护）
        idx = getattr(node, "_idx", None)
        n = len(idx)
        node.n_samples = n
        if depth >= self.max_depth or n < self.min_samples_split:
            node.value = float(np.mean(y[idx]))
            return
        rng = np.random.default_rng(self.seed + len(self.nodes))
        f, t = self._best_split(X, y, idx, rng)
        if f is None:
            node.value = float(np.mean(y[idx]))
            return
        left_mask = X[idx, f] <= t
        li = np.where(left_mask)[0]
        ri = np.where(~left_mask)[0]
        if len(li) < self.min_samples_leaf or len(ri) < self.min_samples_leaf:
            node.value = float(np.mean(y[idx]))
            return
        node.feature, node.threshold = f, t
        lnode = _Node()
        rnode = _Node()
        # 用临时属性携带子集索引，生长完成后清除
        lnode._idx = idx[li]
        rnode._idx = idx[ri]
        li_node = self._new_node()
        ri_node = self._new_node()
        self.nodes[li_node] = lnode
        self.nodes[ri_node] = rnode
        node.left = li_node
        node.right = ri_node
        self._grow(X, y, lnode, depth + 1)
        self._grow(X, y, rnode, depth + 1)

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.empty(X.shape[0])
        for i in range(X.shape[0]):
            out[i] = self._predict_row(X[i])
        return out

    def _predict_row(self, row):
        node = self.nodes[0]
        # 用迭代而非递归，避免深度大时 Python 递归栈过深
        while node.feature is not None:
            if row[node.feature] <= node.threshold:
                node = self.nodes[node.left]
            else:
                node = self.nodes[node.right]
        return node.value


class RandomForestRegressor:
    """随机森林回归，sklearn 优先 / numpy 回退。

    参数固定按 skill spec：n_estimators=103, min_samples_split=3,
    min_samples_leaf=2, max_depth=10。
    """

    def __init__(self, n_estimators=103, min_samples_split=3,
                 min_samples_leaf=2, max_depth=10, max_features="sqrt",
                 random_state=0, n_jobs=1):
        self.n_estimators = n_estimators
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_depth = max_depth
        self.max_features = max_features
        self.random_state = random_state
        self.n_jobs = n_jobs
        self._skrf_cls = _try_import_sklearn()
        self._sk_model = None
        self._trees = None
        self._feature_importances_ = None
        self.n_features_in_ = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.n_features_in_ = X.shape[1]
        mtry = None
        if isinstance(self.max_features, str):
            if self.max_features == "sqrt":
                mtry = max(1, int(math.sqrt(X.shape[1])))
            elif self.max_features == "log2":
                mtry = max(1, int(math.log2(X.shape[1])))
            else:
                mtry = X.shape[1]
        else:
            mtry = self.max_features

        if self._skrf_cls is not None:
            self._sk_model = self._skrf_cls(
                n_estimators=self.n_estimators,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                max_depth=self.max_depth,
                max_features=self.max_features,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )
            self._sk_model.fit(X, y)
            self._feature_importances_ = np.asarray(
                self._sk_model.feature_importances_, dtype=float)
            return self

        # ---- numpy 回退 ----
        self._trees = []
        rng = np.random.default_rng(self.random_state)
        n = X.shape[0]
        # 特征重要性：累计每次分裂的方差下降（加权样本占比），
        # 这是 sklearn 默认 gini/方差重要性口径的近似，最后按特征归一化。
        imp_counts = np.zeros(X.shape[1])
        for t in range(self.n_estimators):
            boot = rng.integers(0, n, size=n)
            Xb, yb = X[boot], y[boot]
            tree = _NumpyDecisionTree(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                max_features=mtry,
                seed=self.random_state + t,
            )
            # 通过 fit 时传入样本索引的方式生长
            self._fit_tree_with_indices(tree, Xb, yb, imp_counts)
            self._trees.append(tree)
        s = imp_counts.sum()
        if s > 0:
            self._feature_importances_ = imp_counts / s
        else:
            self._feature_importances_ = np.ones(X.shape[1]) / X.shape[1]
        return self

    def _fit_tree_with_indices(self, tree, X, y, imp_counts=None):
        """适配 _NumpyDecisionTree 需要 _idx 属性的生长方式。"""
        root = _Node()
        root._idx = np.arange(len(y))
        # 复用 tree 的节点列表结构
        tree.nodes = [root]
        self._grow_with(tree, X, y, root, 0, imp_counts)
        # 清理临时 _idx
        for nd in tree.nodes:
            if hasattr(nd, "_idx"):
                del nd._idx
        return tree

    def _grow_with(self, tree, X, y, node, depth, imp_counts=None):
        idx = node._idx
        n = len(idx)
        node.n_samples = n
        if depth >= tree.max_depth or n < tree.min_samples_split:
            node.value = float(np.mean(y[idx]))
            return
        rng = np.random.default_rng(tree.seed + len(tree.nodes))
        f, t, gain = self._best_split_with(tree, X, y, idx, rng)
        if f is None:
            node.value = float(np.mean(y[idx]))
            return
        left_mask = X[idx, f] <= t
        li = np.where(left_mask)[0]
        ri = np.where(~left_mask)[0]
        if len(li) < tree.min_samples_leaf or len(ri) < tree.min_samples_leaf:
            node.value = float(np.mean(y[idx]))
            return
        node.feature, node.threshold = f, t
        if imp_counts is not None:
            imp_counts[f] += gain * n
        lnode, rnode = _Node(), _Node()
        lnode._idx = idx[li]
        rnode._idx = idx[ri]
        tree.nodes.append(lnode)
        tree.nodes.append(rnode)
        node.left = len(tree.nodes) - 2
        node.right = len(tree.nodes) - 1
        self._grow_with(tree, X, y, lnode, depth + 1, imp_counts)
        self._grow_with(tree, X, y, rnode, depth + 1, imp_counts)

    def _best_split_with(self, tree, X, y, idx, rng):
        n = len(idx)
        if n < tree.min_samples_split:
            return None, None, 0.0
        p = X.shape[1]
        mtry = tree.max_features if tree.max_features is not None else max(1, int(math.sqrt(p)))
        feats = rng.choice(p, size=min(mtry, p), replace=False)
        y_sub = y[idx]
        parent_var = float(np.var(y_sub))
        if parent_var < 1e-15:
            return None, None, 0.0
        best_gain, best_f, best_t = -1.0, None, None
        for f in feats:
            vals = X[idx, f]
            order = np.argsort(vals, kind="mergesort")
            v_sorted = vals[order]
            uniq = np.unique(v_sorted)
            if uniq.shape[0] < 2:
                continue
            cand = (uniq[:-1] + uniq[1:]) / 2.0
            y_sorted = y_sub[order]
            cs = np.cumsum(y_sorted)
            cs2 = np.cumsum(y_sorted * y_sorted)
            left_pos = np.searchsorted(v_sorted, cand, side="right")
            for t, ln in zip(cand, left_pos):
                if ln < tree.min_samples_leaf or (n - ln) < tree.min_samples_leaf:
                    continue
                s_left = cs[ln - 1] if ln > 0 else 0.0
                s2_left = cs2[ln - 1] if ln > 0 else 0.0
                s_right = cs[-1] - s_left
                s2_right = cs2[-1] - s2_left
                var_l = s2_left / ln - (s_left / ln) ** 2
                var_r = s2_right / (n - ln) - (s_right / (n - ln)) ** 2
                gain = parent_var - (ln / n) * var_l - ((n - ln) / n) * var_r
                if gain > best_gain:
                    best_gain, best_f, best_t = gain, int(f), float(t)
        return best_f, best_t, best_gain

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        if self._sk_model is not None:
            return np.asarray(self._sk_model.predict(X), dtype=float)
        preds = np.column_stack([t.predict(X) for t in self._trees])
        return preds.mean(axis=1)

    @property
    def feature_importances_(self):
        return self._feature_importances_

    @property
    def backend(self):
        if self._sk_model is not None:
            return "sklearn"
        if self._trees is not None:
            return "numpy"
        return "not_fitted"


if __name__ == "__main__":
    # 快速自检：numpy 回退能跑通一个玩具回归
    rng = np.random.default_rng(42)
    X = rng.normal(size=(300, 4))
    y = 2 * X[:, 0] - 1.5 * X[:, 1] + 0.5 * X[:, 2] + rng.normal(size=300) * 0.3
    rf = RandomForestRegressor()
    rf.fit(X, y)
    pred = rf.predict(X[:10])
    print("backend:", rf.backend)
    print("feature_importances_:", np.round(rf.feature_importances_, 4))
    print("pred sample:", np.round(pred, 4))
    print("自检 OK")
