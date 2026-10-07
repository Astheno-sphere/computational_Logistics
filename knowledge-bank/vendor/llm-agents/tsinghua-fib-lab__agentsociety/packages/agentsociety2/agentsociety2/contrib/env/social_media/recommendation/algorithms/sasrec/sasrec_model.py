"""
SASRec模型实现（Self-Attentive Sequential Recommendation）
"""

import numpy as np
import torch
from torch import nn


class PointWiseFeedForward(nn.Module):
    """
    逐点前馈神经网络（Point-wise Feed-Forward Network）

    用于Transformer块中的FFN层，使用两层1D卷积实现。
    结构：Conv1D -> Dropout -> ReLU -> Conv1D -> Dropout + 残差连接

    :param hidden_units: 隐藏层维度
    :param dropout_rate: Dropout概率
    """

    def __init__(self, hidden_units, dropout_rate):
        super().__init__()

        self.conv1 = torch.nn.Conv1d(hidden_units, hidden_units, kernel_size=1)
        self.dropout1 = torch.nn.Dropout(p=dropout_rate)
        self.relu = torch.nn.ReLU()
        self.conv2 = torch.nn.Conv1d(hidden_units, hidden_units, kernel_size=1)
        self.dropout2 = torch.nn.Dropout(p=dropout_rate)

    def forward(self, inputs):
        # Conv1D需要(N, C, Length)格式，所以需要转置
        outputs = self.dropout2(
            self.conv2(self.relu(self.dropout1(self.conv1(inputs.transpose(-1, -2)))))
        )
        outputs = outputs.transpose(-1, -2)  # 转回(N, Length, C)
        outputs += inputs  # 残差连接
        return outputs


class SASRec(nn.Module):
    """
    SASRec: Self-Attentive Sequential Recommendation

    :param args: 配置对象，需包含以下字段： - user_num (int): 用户数量 - item_num (int): 物品数量 - hidden_units (int): 隐藏层维度（嵌入维度） - maxlen (int): 最大序列长度 - num_blocks (int): Transformer块数量 - num_heads (int): 注意力头数 - dropout_rate (float): Dropout概率

    输入：
        - seqs (Tensor): 用户行为序列 [batch_size, max_len]
        - target (Tensor): 目标物品ID [batch_size] 或 [batch_size, K]
        - target_posi (Tensor, optional): 目标位置索引 [batch_size, 2]

    输出：
        - scores (Tensor): 预测分数 [batch_size] 或 [batch_size, K]
    """

    def __init__(self, args):
        super().__init__()
        self.config = args

        self.user_num = args.user_num
        self.item_num = args.item_num

        # 物品嵌入层（padding_idx=0表示ID=0为填充符）
        self.item_emb = torch.nn.Embedding(
            self.item_num, args.hidden_units, padding_idx=0
        )

        # 位置编码层（可学习的位置嵌入）
        self.pos_emb = torch.nn.Embedding(args.maxlen, args.hidden_units)

        # Embedding Dropout
        self.emb_dropout = torch.nn.Dropout(p=args.dropout_rate)

        # Transformer块列表
        self.attention_layernorms = torch.nn.ModuleList()  # 注意力层前的LayerNorm
        self.attention_layers = torch.nn.ModuleList()  # 多头自注意力层
        self.forward_layernorms = torch.nn.ModuleList()  # FFN前的LayerNorm
        self.forward_layers = torch.nn.ModuleList()  # 前馈神经网络

        # 最终的LayerNorm
        self.last_layernorm = torch.nn.LayerNorm(args.hidden_units, eps=1e-8)

        # 构建num_blocks个Transformer块
        for _ in range(args.num_blocks):
            # 注意力子层
            new_attn_layernorm = torch.nn.LayerNorm(args.hidden_units, eps=1e-8)
            self.attention_layernorms.append(new_attn_layernorm)

            new_attn_layer = torch.nn.MultiheadAttention(
                args.hidden_units, args.num_heads, args.dropout_rate
            )
            self.attention_layers.append(new_attn_layer)

            # FFN子层
            new_fwd_layernorm = torch.nn.LayerNorm(args.hidden_units, eps=1e-8)
            self.forward_layernorms.append(new_fwd_layernorm)

            new_fwd_layer = PointWiseFeedForward(args.hidden_units, args.dropout_rate)
            self.forward_layers.append(new_fwd_layer)

        # 初始化设备属性（避免AttributeError）
        self.dev = self.item_emb.weight.device

    def _device(self):
        """获取模型所在设备（更新self.dev）"""
        self.dev = self.item_emb.weight.device

    def log2feats(self, log_seqs):
        """
        将用户行为序列编码为特征向量

        处理流程：
        1. Item Embedding + 缩放
        2. Position Embedding
        3. Dropout
        4. 应用Padding Mask
        5. 通过多个Transformer块（Self-Attention + FFN）
        6. 最终LayerNorm

        :param log_seqs: 用户行为序列 [batch_size, seq_len]

        :returns: log_feats (Tensor): 序列特征 [batch_size, seq_len, hidden_units]
        """
        # 1. 物品嵌入 + 缩放（类似Transformer论文中的sqrt(d_model)缩放）
        seqs = self.item_emb(log_seqs.to(self.dev))
        seqs *= self.item_emb.embedding_dim**0.5

        # 2. 位置编码（为每个位置添加位置信息）
        positions = np.tile(np.array(range(log_seqs.shape[1])), [log_seqs.shape[0], 1])
        seqs += self.pos_emb(torch.LongTensor(positions).to(self.dev))
        seqs = self.emb_dropout(seqs)

        # 3. Padding mask（将padding位置（ID=0）的向量置零）
        timeline_mask = torch.BoolTensor(log_seqs.cpu().numpy() == 0).to(self.dev)
        seqs *= ~timeline_mask.unsqueeze(-1)  # 广播到最后一维

        # 4. Causal attention mask（因果遮蔽，防止未来信息泄露）
        tl = seqs.shape[1]  # 序列长度
        attention_mask = ~torch.tril(
            torch.ones((tl, tl), dtype=torch.bool, device=self.dev)
        )

        # 5. 通过Transformer块
        for i in range(len(self.attention_layers)):
            # 自注意力子层（Pre-LN架构）
            seqs = torch.transpose(
                seqs, 0, 1
            )  # MultiheadAttention需要(seq_len, batch, embed)
            Q = self.attention_layernorms[i](seqs)
            mha_outputs, _ = self.attention_layers[i](
                Q, seqs, seqs, attn_mask=attention_mask
            )
            seqs = Q + mha_outputs  # 残差连接
            seqs = torch.transpose(seqs, 0, 1)  # 转回(batch, seq_len, embed)

            # FFN子层
            seqs = self.forward_layernorms[i](seqs)
            seqs = self.forward_layers[i](seqs)
            seqs *= ~timeline_mask.unsqueeze(-1)  # 重新应用padding mask

        # 6. 最终LayerNorm
        log_feats = self.last_layernorm(seqs)  # [batch_size, seq_len, hidden_units]

        return log_feats

    def forward(self, seqs, target, target_posi=None):
        """
        前向传播：计算序列-物品匹配分数

        :param seqs: 用户行为序列 [batch_size, seq_len]
        :param target: 目标物品ID [batch_size] 或 [batch_size, K]
        :param target_posi: 目标位置索引 [N, 2]，格式为[batch_idx, seq_idx]

        :returns: scores (Tensor): 预测分数 [batch_size] 或 [N]
        """
        self._device()

        # 序列编码
        log_feats = self.log2feats(seqs)

        # 提取序列表示
        if target_posi is not None:
            # 从指定位置提取特征
            s_emb = log_feats[target_posi[:, 0], target_posi[:, 1]]
        else:
            # 默认使用最后一个时间步的特征
            s_emb = log_feats[:, -1, :]

        # 目标物品嵌入
        target_embeds = self.item_emb(target.reshape(-1))

        # 计算匹配分数（内积）
        scores = torch.mul(s_emb, target_embeds).sum(dim=-1)

        return scores

    def forward_eval(self, user_ids, target_item, log_seqs):
        """
        评估时的前向传播（仅使用最后一个时间步）

        :param user_ids: 用户ID（未使用，保留接口兼容性）
        :param target_item: 目标物品ID [batch_size]
        :param log_seqs: 用户行为序列 [batch_size, seq_len]

        :returns: scores (Tensor): 预测分数 [batch_size]
        """
        self._device()
        log_feats = self.log2feats(log_seqs)

        # 使用最后一个时间步
        log_feats = log_feats[:, -1, :]
        item_embs = self.item_emb(target_item)

        return (log_feats * item_embs).sum(dim=-1)

    def computer(self):
        """
        兼容接口：返回None（SASRec不使用预计算的用户/物品表示）
        """
        return None, None

    def seq_encoder(self, seqs):
        """
        序列编码器：将行为序列编码为用户表示

        :param seqs: 用户行为序列 [batch_size, seq_len]

        :returns: seq_emb (Tensor): 序列嵌入（最后时间步） [batch_size, hidden_units]
        """
        self._device()
        log_feats = self.log2feats(seqs)
        seq_emb = log_feats[:, -1, :]
        return seq_emb

    def item_encoder(self, target_item, all_items=None):
        """
        物品编码器：获取物品嵌入

        :param target_item: 目标物品ID
        :param all_items: 未使用，保留接口兼容性

        :returns: target_embeds (Tensor): 物品嵌入
        """
        self._device()
        target_embeds = self.item_emb(target_item)
        return target_embeds

    def predict(self, user_ids, log_seqs, item_indices):
        """
        预测接口：为指定物品列表计算分数

        :param user_ids: 用户ID（未使用）
        :param log_seqs: 用户行为序列 [batch_size, seq_len]
        :param item_indices: 物品ID列表 [num_items]

        :returns: logits (Tensor): 预测logits [batch_size, num_items]
        """
        log_feats = self.log2feats(log_seqs)

        final_feat = log_feats[:, -1, :]  # 使用最后一个QKV状态

        item_embs = self.item_emb(
            torch.LongTensor(item_indices).to(self.dev)
        )  # [num_items, hidden_units]

        logits = item_embs.matmul(final_feat.unsqueeze(-1)).squeeze(-1)

        return logits

    def predict_all(self, user_ids, log_seqs):
        """
        预测所有物品的分数

        :param user_ids: 用户ID（未使用）
        :param log_seqs: 用户行为序列 [batch_size, seq_len]

        :returns: logits (Tensor): 所有物品的预测logits [batch_size, item_num]
        """
        log_feats = self.log2feats(log_seqs)

        final_feat = log_feats[:, -1, :]  # 取最后时间步

        item_embs = self.item_emb.weight  # 所有物品的嵌入 [item_num, hidden_units]

        # 计算用户表示与所有物品的匹配分数
        logits = torch.matmul(final_feat, item_embs.T)  # [batch_size, item_num]

        return logits

    def predict_all_batch(self, user_ids, log_seqs, batch_size=128):
        """
        批量预测所有物品（与predict_all功能相同，保留接口兼容性）

        :param user_ids: 用户ID（未使用）
        :param log_seqs: 用户行为序列 [batch_size, seq_len]
        :param batch_size: 批大小（未使用）

        :returns: logits (Tensor): 所有物品的预测logits [batch_size, item_num]
        """
        log_feats = self.log2feats(log_seqs)
        final_feat = log_feats[:, -1, :]
        item_embs = self.item_emb.weight
        logits = torch.matmul(final_feat, item_embs.T)
        return logits

    def log2feats_v2(self, log_seqs, emb_replace=None):
        """
        序列编码（支持嵌入替换）- 用于特殊场景

        :param log_seqs: 用户行为序列（可包含负数ID）
        :param emb_replace: 替换嵌入（用于负数ID位置）

        :returns: log_feats: 序列特征
        """
        log_seqs = log_seqs + 0

        # 处理负数ID（作为特殊标记）
        emb_replace_idx = np.where(log_seqs < 0)
        log_seqs[emb_replace_idx] = 0
        seqs = self.item_emb(torch.LongTensor(log_seqs).to(self.dev)) + 0
        log_seqs[emb_replace_idx] = -1

        # 替换特殊位置的嵌入
        if emb_replace is not None:
            seqs[emb_replace_idx[0], emb_replace_idx[1]] = 0
            seqs[emb_replace_idx[0], emb_replace_idx[1]] += emb_replace

        seqs *= self.item_emb.embedding_dim**0.5
        positions = np.tile(np.array(range(log_seqs.shape[1])), [log_seqs.shape[0], 1])
        seqs += self.pos_emb(torch.LongTensor(positions).to(self.dev))
        seqs = self.emb_dropout(seqs)

        timeline_mask = torch.BoolTensor(log_seqs == 0).to(self.dev)
        seqs *= ~timeline_mask.unsqueeze(-1)

        tl = seqs.shape[1]
        attention_mask = ~torch.tril(
            torch.ones((tl, tl), dtype=torch.bool, device=self.dev)
        )

        for i in range(len(self.attention_layers)):
            seqs = torch.transpose(seqs, 0, 1)
            Q = self.attention_layernorms[i](seqs)
            mha_outputs, _ = self.attention_layers[i](
                Q, seqs, seqs, attn_mask=attention_mask
            )
            seqs = Q + mha_outputs
            seqs = torch.transpose(seqs, 0, 1)

            seqs = self.forward_layernorms[i](seqs)
            seqs = self.forward_layers[i](seqs)
            seqs *= ~timeline_mask.unsqueeze(-1)

        log_feats = self.last_layernorm(seqs)
        return log_feats

    def predict_position(self, log_seqs, positions, emb_replace=None):
        """
        预测指定位置的物品（用于特殊训练策略）

        :param log_seqs: 用户行为序列
        :param positions: 目标位置索引
        :param emb_replace: 替换嵌入

        :returns: logits: 预测logits
        """
        log_feats = self.log2feats_v2(log_seqs, emb_replace=emb_replace)

        final_feat = log_feats[np.arange(positions.shape[0]), positions]

        item_embs = self.item_emb.weight

        logits = torch.matmul(final_feat, item_embs.T)

        return logits
