import warnings
warnings.filterwarnings('ignore')

import torch
from torch import nn
import torch.nn.functional as F

n_classes = 6
n_input = 9
n_hidden = 32

n_classes = 6
n_input = 9
n_hidden = 32


class BiDirResidual_LSTMModel(nn.Module):

    def __init__(self, n_input=n_input, n_hidden=n_hidden, n_layers=2,
                 n_classes=n_classes, drop_prob=0.5):
        super(BiDirResidual_LSTMModel, self).__init__()

        self.n_layers = n_layers
        self.n_hidden = n_hidden
        self.n_classes = n_classes
        self.drop_prob = drop_prob
        self.n_input = n_input

        self.relu1 = nn.Sequential(
            nn.Linear(n_input, n_input),
            nn.ReLU()
        )
        self.relu2 = nn.Sequential(
            nn.Linear(n_hidden, n_hidden),
            nn.ReLU()
        )
        self.lstm = nn.LSTM(n_input, n_hidden, n_layers, dropout=self.drop_prob)
        self.bidir_lstm1 = nn.LSTM(n_input, int(n_hidden / 2), n_layers, bidirectional=True, dropout=self.drop_prob)
        self.bidir_lstm2 = nn.LSTM(n_hidden, int(n_hidden / 2), n_layers, bidirectional=True, dropout=self.drop_prob)
        self.fc = nn.Linear(n_hidden, n_classes)
        self.BatchNorm = nn.BatchNorm1d(100)
        self.dropout = nn.Dropout(drop_prob)
        self.count=1

    def add_residual_component(self, layer1, layer2):
        return torch.add(layer1, layer2)

    def make_residual_layer(self, input_layer, hidden, first=False):
        if first:
            mid_layer, hidden_layer1 = self.bidir_lstm1(input_layer, hidden)
        else:
            mid_layer, hidden_layer1 = self.bidir_lstm2(input_layer, hidden)

        mid_layer = self.relu2(mid_layer)
        output_layer, hidden_layer2 = self.bidir_lstm2(mid_layer, hidden)
        output_layer = self.relu2(output_layer)

        output = self.add_residual_component(mid_layer, output_layer)
        output = self.BatchNorm(output)
        return output

    def forward(self, x, hidden):
        #print("Shape of input is: {}".format(x.shape))
        x = x.permute(1, 0, 2)

        x = self.relu1(x)
        x = self.make_residual_layer(x, hidden, first=True)
        x = self.make_residual_layer(x, hidden, first=False)
        x = self.dropout(x)
        if self.count==1:
            print("Shape of x is: {}".format(x.shape))
            self.count=0
        out = x[-1]
        out = out.contiguous().view(-1, self.n_hidden)
        out = self.fc(out)
        out = F.softmax(out)
        #print("Shape of out is: {}".format(out.shape))

        return out

    def init_hidden(self, batch_size):
        ''' Initialize hidden state'''
        # Create two new tensors with sizes n_layers x batch_size x n_hidden,
        # initialized to zero, for hidden state and cell state of LSTM
        weight = next(self.parameters()).data

        # if (train_on_gpu):
        if (torch.cuda.is_available()):
            hidden = (weight.new(2 * self.n_layers, batch_size, int(self.n_hidden / 2)).zero_().cuda(),
                      weight.new(2 * self.n_layers, batch_size, int(self.n_hidden / 2)).zero_().cuda())
        else:
            hidden = (weight.new(2 * self.n_layers, batch_size, int(self.n_hidden / 2)).zero_(),
                      weight.new(2 * self.n_layers, batch_size, int(self.n_hidden / 2)).zero_())

        return hidden


def init_weights(m):
    if type(m) == nn.LSTM:
        for name, param in m.named_parameters():
            if 'weight_ih' in name:
                torch.nn.init.orthogonal_(param.data)
            elif 'weight_hh' in name:
                torch.nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                param.data.fill_(0)
    elif type(m) == nn.Linear:
        torch.nn.init.orthogonal_(m.weight)
        m.bias.data.fill_(0)
