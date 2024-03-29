import torch
from torch import nn
from d2l import torch as d2l

#@save
def get_tokens_and_segments(tokens_a, tokens_b=None):
    """获取输入序列的词元及其片段索引"""
    tokens = ['<cls>'] + tokens_a + ['<sep>']
    # 0和1分别标记片段A和B
    segments = [0] * (len(tokens_a) + 2)
    if tokens_b is not None:
        tokens += tokens_b + ['<sep>']
        segments += [1] * (len(tokens_b) + 1)
    return tokens, segments



#@save
class BERTEncoder(nn.Module):
    """BERT编码器"""
    def __init__(self, vocab_size, num_hiddens, norm_shape, ffn_num_input,
                 ffn_num_hiddens, num_heads, num_layers, dropout,
                 max_len=1000, key_size=768, query_size=768, value_size=768,
                 **kwargs):
        super(BERTEncoder, self).__init__(**kwargs)
        self.token_embedding = nn.Embedding(vocab_size, num_hiddens)
        self.segment_embedding = nn.Embedding(2, num_hiddens)
        self.blks = nn.Sequential()
        for i in range(num_layers):#transformer block
            self.blks.add_module(f"{i}", d2l.EncoderBlock(
                key_size, query_size, value_size, num_hiddens, norm_shape,
                ffn_num_input, ffn_num_hiddens, num_heads, dropout, True))
        # 在BERT中，位置嵌入是可学习的，因此我们创建一个足够长的位置嵌入参数
        self.pos_embedding = nn.Parameter(torch.randn(1, max_len,
                                                      num_hiddens))

    def forward(self, tokens, segments, valid_lens):
        # 在以下代码段中，X的形状保持不变：（批量大小，最大序列长度，num_hiddens）
        X = self.token_embedding(tokens) + self.segment_embedding(segments)
        #print("self.token_embedding(tokens):", self.token_embedding(tokens).shape)
        #print("self.segment_embedding(segments):", self.segment_embedding(segments).shape)
        X = X + self.pos_embedding.data[:, :X.shape[1], :]
        #print("self.pos_embedding.data[:, :X.shape[1], :]:", self.pos_embedding.data[:, :X.shape[1], :].shape)
        
        #把embedding输入到block中
        for blk in self.blks:
            X = blk(X, valid_lens)
        return X
    
#词汇表大小、隐藏单元数、FFN隐藏层的隐藏单元数、多头注意力头数
vocab_size, num_hiddens, ffn_num_hiddens, num_heads = 10000, 768, 1024, 4

#layer norm shape，ffn输入层维度，transformer block个数，dropout
norm_shape, ffn_num_input, num_layers, dropout = [768], 768, 2, 0.2
encoder = BERTEncoder(vocab_size, num_hiddens, norm_shape, ffn_num_input,
                      ffn_num_hiddens, num_heads, num_layers, dropout)


tokens = torch.randint(0, vocab_size, (2, 8)) # (batch_size, max_len)
segments = torch.tensor([[0, 0, 0, 0, 1, 1, 1, 1], [0, 0, 0, 1, 1, 1, 1, 1]])#(batch_size, max_len)
encoded_X = encoder(tokens, segments, None)#torch.Size([batch_size, max_len, num_hiddens])
#print(encoded_X)
#print(encoded_X.shape)

#@save
class MaskLM(nn.Module):
    """BERT的掩蔽语言模型任务"""
    def __init__(self, vocab_size, num_hiddens, num_inputs=768, **kwargs):
        super(MaskLM, self).__init__(**kwargs)
        self.mlp = nn.Sequential(nn.Linear(num_inputs, num_hiddens),
                                 nn.ReLU(),
                                 nn.LayerNorm(num_hiddens),
                                 nn.Linear(num_hiddens, vocab_size))

    def forward(self, X, pred_positions):
        """
        X是BERT Encoder的ouput, shape: (batch_size, max_len, num_hiddens)
        pred_positions是掩蔽语言模型任务的预测位置, shape: (batch_size, num_mlm_preds)
        """
        num_pred_positions = pred_positions.shape[1]
        pred_positions = pred_positions.reshape(-1)
        batch_size = X.shape[0]
        batch_idx = torch.arange(0, batch_size)#（[0,0,0,1,1,1]）
        print("batch_idx:", batch_idx)#([0, 1])
        # 假设batch_size=2，num_pred_positions=3
        # 那么batch_idx是np.array（[0,0,0,1,1,1]）
        batch_idx = torch.repeat_interleave(batch_idx, num_pred_positions)
        print("batch_idx:", batch_idx)#（[0,0,0,1,1,1]）
        masked_X = X[batch_idx, pred_positions]
        print( "X:", X.shape)
        print("pred_positions:", pred_positions.shape)
        masked_X = masked_X.reshape((batch_size, num_pred_positions, -1))
        mlm_Y_hat = self.mlp(masked_X)
        return mlm_Y_hat

mlm = MaskLM(vocab_size, num_hiddens)
mlm_positions = torch.tensor([[1, 5, 2], [6, 1, 5]])
mlm_Y_hat = mlm(encoded_X, mlm_positions)
print(mlm_Y_hat.shape)#torch.Size([batch_size, num_mlm_preds, vocab_size])


mlm_Y = torch.tensor([[7, 8, 9], [10, 20, 30]])
loss = nn.CrossEntropyLoss(reduction='none')
mlm_l = loss(mlm_Y_hat.reshape((-1, vocab_size)), mlm_Y.reshape(-1))
print(mlm_l.shape)
