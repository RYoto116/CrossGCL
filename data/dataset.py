import pandas as pd
import numpy as np
import os
from collections import OrderedDict
import warnings
from copy import deepcopy
from reckit.util.decorators import typeassert
import scipy.sparse as sp

_USER = "user"
_ITEM = "item"
_RATING = "rating"
_TIME = "time"
_column_dict = {"UI": [_USER, _ITEM]#,
                # "UIR": [_USER, _ITEM, _RATING],
                # "UIT": [_USER, _ITEM, _TIME],
                # "UIRT": [_USER, _ITEM, _RATING, _TIME]
                }

class Interaction(object):
    @typeassert(data=(pd.DataFrame, None), num_users=(int, None), num_items=(int, None))
    def __init__(self, data=None, num_users=None, num_items=None):
        if data is None or data.empty:
            self._data = pd.DataFrame()
            self.num_users = 0
            self.num_items = 0
            self.num_ratings = 0
        else:
            self._data = data
            self.num_users = num_users if num_users is not None else max(data[_USER] + 1)
            self.num_items = num_items if num_items is not None else max(data[_ITEM] + 1)
            self.num_ratings = len(data)
        self._buffer = dict()

    # groupby: 每个用户对应交互商品的字典
    def to_user_dict(self):
        if self._data.empty:
            warnings.warn("self._data is empty.")
            return None

        user_dict = OrderedDict()
        user_grouped = self._data.groupby(_USER)
        for user, data in user_grouped:
            user_dict[user] = data[_ITEM].to_numpy(dtype=np.int32)

        self._buffer["user_dict"] = deepcopy(user_dict)
        return user_dict
    
    def to_csr_matrix(self):
        if self._data.empty:
            warnings.warn("self._data is empty.")
            return None
        users, items = self._data[_USER].to_numpy(), self._data[_ITEM].to_numpy()
        ratings = np.ones(len(users), dtype=np.float32)
        csr_mat = sp.csr_matrix((ratings, (users, items)), shape=(self.num_users, self.num_items))
        return csr_mat

    def to_user_item_pairs(self):
        if self._data.empty:
            warnings.warn("self._data is empty.")
            return None
        return self._data[[_USER, _ITEM]].to_numpy(copy=True, dtype=np.int32)

    def __len__(self):
        return len(self._data)


class Dataset(object):
    def __init__(self, data_dir, dataset_name, sep, columns):
        self._data_dir = data_dir
        self.data_name = dataset_name

        self.train_data = Interaction()
        self.valid_data = Interaction()
        self.test_data = Interaction()
        # self.user2id = None
        # self.item2id = None
        # self.id2user = None
        # self.id2item = None

        self.num_users = 0
        self.num_items = 0
        self.num_ratings = 0

        # 加载原始数据
        if columns not in _column_dict:
            raise ValueError("'columns' must be one of '%s'." % ", ".join(_column_dict.keys()))
        columns = _column_dict[columns]
        prefix = os.path.join(data_dir, dataset_name, dataset_name)

        train_file = prefix + ".train"
        if os.path.isfile(train_file):
            _train_data = pd.read_csv(train_file, sep=sep, header=None, names=columns)
        else:
            raise FileNotFoundError(f"{train_file} does not exist.")

        valid_file = prefix + ".valid"
        if os.path.isfile(valid_file):
            _valid_data = pd.read_csv(valid_file, sep=sep, header=None, names=columns)
        else:
            _valid_data = pd.DataFrame()
            warnings.warn("valid_file does not exist.")

        test_file = prefix + ".test"
        if os.path.isfile(test_file):
            _test_data = pd.read_csv(test_file, sep=sep, header=None, names=columns)
        else:
            raise FileNotFoundError(f"{test_file} does not exist.")

        # user2id_file = prefix + ".user2id"
        # if os.path.isfile(user2id_file):
        #     _user2id = pd.read_csv(user2id_file, sep=sep, header=None, names=columns)
        #     self.user2id = OrderedDict(_user2id)
        #     self.id2user = OrderedDict([(idx, user) for user, idx in self.user2id.items()])
        # else:
        #     warnings.warn(f"{user2id_file} does not exist.")

        # item2id_file = prefix + ".item2id"
        # if os.path.isfile(item2id_file):
        #     _item2id = pd.read_csv(item2id_file, sep=sep, header=None, names=columns)
        #     self.item2id = OrderedDict(_item2id)
        #     self.id2item = OrderedDict([(idx, item) for item, idx in self.item2id.items()])
        # else:
        #     warnings.warn(f"{item2id_file} does not exist.")

        data_list = [data for data in [_train_data, _valid_data, _test_data] if not data.empty]
        all_data = pd.concat(data_list)
        self.num_users = max(all_data[_USER]) + 1
        self.num_items = max(all_data[_ITEM]) + 1
        self.num_ratings = len(all_data)
        self.num_train_ratings = len(_train_data)

        # 转换为Interaction对象
        self.train_data = Interaction(_train_data, self.num_users, self.num_items)
        self.valid_data = Interaction(_valid_data, self.num_users, self.num_items)
        self.test_data = Interaction(_test_data, self.num_users, self.num_items)
        
        self.train_csr_mat = self.train_data.to_csr_matrix()
        self.item_degrees = self._count_item_frequency()

    def __str__(self):
        if 0 in {self.num_users, self.num_items, self.num_ratings}:
            return "statistical information is unavailable now"
        else:
            num_users, num_items = self.num_users, self.num_items
            num_ratings = self.num_ratings
            sparsity = 1 - 1.0 * num_ratings / (num_users * num_items)

            statistic = ["Dataset statistics:",
                         "Name: %s" % self.data_name,
                         "The number of users: %d" % num_users,
                         "The number of items: %d" % num_items,
                         "The number of ratings: %d" % num_ratings,
                         "Average actions of users: %.2f" % (1.0 * num_ratings / num_users),
                         "Average actions of items: %.2f" % (1.0 * num_ratings / num_items),
                         "The sparsity of the dataset: %.6f%%" % (sparsity * 100),
                         "",
                         "The number of training: %d" % len(self.train_data),
                         "The number of validation: %d" % len(self.valid_data),
                         "The number of testing: %d" % len(self.test_data)
                         ]
            statistic = "\n".join(statistic)
            return statistic

    def __repr__(self):
        return self.__str__()

    def _count_item_frequency(self):
        colsum = np.array(self.train_csr_mat.sum(0))
        return np.squeeze(colsum)

    def _count_user_frequency(self):
        rowsum = np.array(self.train_csr_mat.sum(1))
        return np.squeeze(rowsum)
