import numpy as np
from Sieve.xcluster.models.PNode import PNode


class WTSampling:
    def __init__(self, dataFile):
        self.dataSet = dataFile

    def build_sliding_tree(self, max_leaves, exact_dist_thres=10):
        root = PNode(exact_dist_thres=exact_dist_thres)
        count = 0
        pt0 = self.dataSet[0]
        length = np.array([pt0[:-1].split(' ')]).shape[1]
        for pt in self.dataSet:
            # 预处理pt
            pts = np.array([pt[:-1].split(' ')]).astype('int')
            # 插入比第一次长的序列会出问题，暂时做截断，后续待优化
            if pts.shape[1] > length:
                pts = pts[:, :length]
            # 插入节点
            if count < max_leaves:
                root = root.insert(pts)
                count += 1
            else:
                self.delete_unlikely_node()
                root = root.insert(pts)
            self.root = root
        self.tree = root

    def delete_unlikely_node(self):
        node = self.root
        while not node.is_leaf():
            node = max(node.children, key=lambda x: x.point_counter)
        sibling = node.siblings()[0]
        parent = node.parent
        parent.children = []
        parent.pts = sibling.pts
        parent.point_counter = sibling.point_counter
        sibling.deleted = True
        node.deleted = True
        parent._update_params_recursively()

    def sampling(self, num, seed=None):
        np.random.seed(seed)
        samples = set()
        sample_count = 0
        count = 0
        while sample_count < num and count < num * 2:
            node = self.root
            while not node.is_leaf():
                node = np.random.choice(node.children, 1)[0]
            if node not in samples:
                samples.add(node)
                sample_count += 1
            count += 1
        return samples


def traceEncoding(traces):
    result = []
    spanMaps = {}
    for index, trace in enumerate(traces):
        spanCount = [0] * len(spanMaps)
        for span in trace.spans:
            label = span.getSpanLabel()
            if label not in spanMaps:
                spanMaps[label] = len(spanMaps)
                spanCount.append(1)
                continue
            spanCount[spanMaps[label]] += 1
        abnormal = 1 if trace.abnormal else 0
        encoding = '%d %d %s\n' % (index, abnormal, ' '.join([str(n) for n in spanCount]))
        index += 1
        result.append(encoding)
    return result
