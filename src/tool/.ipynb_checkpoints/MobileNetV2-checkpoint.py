"""
Creates a MobileNetV2 Model as defined in:
Mark Sandler, Andrew Howard, Menglong Zhu, Andrey Zhmoginov, Liang-Chieh Chen. (2018).
MobileNetV2: Inverted Residuals and Linear Bottlenecks
arXiv preprint arXiv:1801.04381.
import from https://github.com/tonylins/pytorch-mobilenet-v2
"""

import torch.nn as nn
import math
import torch

__all__ = ['mobilenetv2']
try:
    from torch.hub import load_state_dict_from_url
except ImportError:
    from torch.utils.model_zoo import load_url as load_state_dict_from_url


def _make_divisible(v, divisor, min_value=None):
    """
    This function is taken from the original tf repo.
    It ensures that all layers have a channel number that is divisible by 8
    It can be seen here:
    https://github.com/tensorflow/models/blob/master/research/slim/nets/mobilenet/mobilenet.py
    :param v:
    :param divisor:
    :param min_value:
    :return:
    """
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    # Make sure that round down does not go down by more than 10%.
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v


def conv_3x3_bn(inp, oup, stride):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 3, stride, 1, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU6(inplace=True)
    )


def conv_1x1_bn(inp, oup):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 1, 1, 0, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU6(inplace=True)
    )


class InvertedResidual(nn.Module):
    def __init__(self, inp, oup, stride, expand_ratio):
        super(InvertedResidual, self).__init__()
        assert stride in [1, 2]

        hidden_dim = round(inp * expand_ratio)
        self.identity = stride == 1 and inp == oup

        if expand_ratio == 1:
            self.conv = nn.Sequential(
                # dw
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # pw-linear
                nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup),
            )
        else:
            self.conv = nn.Sequential(
                # pw
                nn.Conv2d(inp, hidden_dim, 1, 1, 0, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # dw
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # pw-linear
                nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup),
            )

    def forward(self, x):
        if self.identity:
            return x + self.conv(x)
        else:
            return self.conv(x)


class MobileNetV2(nn.Module):
    def __init__(self, num_classes=1000, width_mult=1.):
        super(MobileNetV2, self).__init__()
        # setting of inverted residual blocks
        self.cfgs1 = [
            # t, c, n, s
            [1, 16, 1, 1],
            [6, 24, 2, 2],
            [6, 32, 3, 2],
            [6, 64, 4, 2],
            [6, 96, 3, 1],
        ]
        self.cfgs2 = [
            # t, c, n, s
            [6, 160, 3, 2],
            [6, 320, 1, 1],
        ]
        # building first layer
        input_channel = _make_divisible(32 * width_mult, 4 if width_mult == 0.1 else 8)
        layers = [conv_3x3_bn(3, input_channel, 2)]
        # building inverted residual blocks
        block = InvertedResidual
        for t, c, n, s in self.cfgs1:
            output_channel = _make_divisible(c * width_mult, 4 if width_mult == 0.1 else 8)
            for i in range(n):
                layers.append(block(input_channel, output_channel, s if i == 0 else 1, t))
                input_channel = output_channel
        self.features = nn.Sequential(*layers)
        layers2 = list()
        for t, c, n, s in self.cfgs2:
            output_channel = _make_divisible(c * width_mult, 4 if width_mult == 0.1 else 8)
            for i in range(n):
                layers2.append(block(input_channel, output_channel, s if i == 0 else 1, t))
                input_channel = output_channel
        self.features2 = nn.Sequential(*layers2)
        # building last several layers
        output_channel = _make_divisible(1280 * width_mult, 4 if width_mult == 0.1 else 8) if width_mult > 1.0 else 1280
        self.conv = conv_1x1_bn(input_channel, output_channel)
        # self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        # self.classifier = nn.Linear(output_channel, num_classes)

        self._initialize_weights()

    def forward(self, x):
        x1 = self.features(x)
        x2 = self.features2(x1)
        x2 = self.conv(x2)
        # x2 = self.avgpool(x2)
        # x2 = x.view(x2.size(0), -1)
        # x2 = self.classifier(x2)
        return x1, x2

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                m.weight.data.normal_(0, 0.01)
                m.bias.data.zero_()


class mnv2_model(nn.module):
    def __init__(self, pretrained):
        super(mnv2_model, self).__init__()
        self.pretrained = pretrained

    def mobilenetv2(self, **kwargs):
        model = MobileNetV2()
        if self.pretrained:
            model_dict = model.state_dict()
            checkpoint = load_state_dict_from_url(self.pretrained, progress=True)
            # pretrained_dict = torch.load(pretrained)['state_dict']

            for k1, v1 in checkpoint.items():
                n1 = k1.replace('module.', '')
                # print(k1)

                for k2, v2 in model_dict.items():
                    n2 = k2.replace('features2.0.', 'features.14.')
                    n2 = n2.replace('features2.1.', 'features.15.')
                    n2 = n2.replace('features2.2.', 'features.16.')
                    n2 = n2.replace('features2.3.', 'features.17.')
                    # print(n1,' , ',n2)
                    if n1 == n2:
                        # print(k1,' , ',k2)
                        model_dict[k2] = v1

            model.load_state_dict(model_dict)
            # torch.save(model, 'test.pth.tar')
        else:
            raise Exception("darknet request a pretrained path. got [{}]".format(pretrained))
        return model



# test()

# import torch.nn as nn
# import math
#
#
# def conv_bn(inp, oup, stride):
#     return nn.Sequential(
#         nn.Conv2d(inp, oup, 3, stride, 1, bias=False),
#         nn.BatchNorm2d(oup),
#         nn.ReLU6(inplace=True)
#     )
#
#
# def conv_1x1_bn(inp, oup):
#     return nn.Sequential(
#         nn.Conv2d(inp, oup, 1, 1, 0, bias=False),
#         nn.BatchNorm2d(oup),
#         nn.ReLU6(inplace=True)
#     )
#
#
# def make_divisible(x, divisible_by=8):
#     import numpy as np
#     return int(np.ceil(x * 1. / divisible_by) * divisible_by)
#
#
# class InvertedResidual(nn.Module):
#     def __init__(self, inp, oup, stride, expand_ratio):
#         super(InvertedResidual, self).__init__()
#         self.stride = stride
#         assert stride in [1, 2]
#
#         hidden_dim = int(inp * expand_ratio)
#         self.use_res_connect = self.stride == 1 and inp == oup
#
#         if expand_ratio == 1:
#             self.conv = nn.Sequential(
#                 # dw
#                 nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
#                 nn.BatchNorm2d(hidden_dim),
#                 nn.ReLU6(inplace=True),
#                 # pw-linear
#                 nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
#                 nn.BatchNorm2d(oup),
#             )
#         else:
#             self.conv = nn.Sequential(
#                 # pw
#                 nn.Conv2d(inp, hidden_dim, 1, 1, 0, bias=False),
#                 nn.BatchNorm2d(hidden_dim),
#                 nn.ReLU6(inplace=True),
#                 # dw
#                 nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
#                 nn.BatchNorm2d(hidden_dim),
#                 nn.ReLU6(inplace=True),
#                 # pw-linear
#                 nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
#                 nn.BatchNorm2d(oup),
#             )
#
#     def forward(self, x):
#         if self.use_res_connect:
#             return x + self.conv(x)
#         else:
#             return self.conv(x)
#
#
# class MobileNetV2(nn.Module):
#     def __init__(self, n_class=1000, input_size=224, width_mult=1.):
#         super(MobileNetV2, self).__init__()
#         block = InvertedResidual
#         input_channel = 32
#         last_channel = 1280
#         interverted_residual_setting = [
#             # t, c, n, s
#             [1, 16, 1, 1],
#             [6, 24, 2, 2],
#             [6, 32, 3, 2],
#             [6, 64, 4, 2],
#             [6, 96, 3, 1],
#             [6, 160, 3, 2],
#             [6, 320, 1, 1],
#         ]
#
#         # building first layer
#         assert input_size % 32 == 0
#         # input_channel = make_divisible(input_channel * width_mult)  # first channel is always 32!
#         self.last_channel = make_divisible(last_channel * width_mult) if width_mult > 1.0 else last_channel
#         self.features = [conv_bn(3, input_channel, 2)]
#         # building inverted residual blocks
#         for t, c, n, s in interverted_residual_setting:
#             output_channel = make_divisible(c * width_mult) if t > 1 else c
#             for i in range(n):
#                 if i == 0:
#                     self.features.append(block(input_channel, output_channel, s, expand_ratio=t))
#                 else:
#                     self.features.append(block(input_channel, output_channel, 1, expand_ratio=t))
#                 input_channel = output_channel
#         # building last several layers
#         self.features.append(conv_1x1_bn(input_channel, self.last_channel))
#         # make it nn.Sequential
#         self.features = nn.Sequential(*self.features)
#
#         # building classifier
#         self.classifier = nn.Linear(self.last_channel, n_class)
#
#         self._initialize_weights()
#
#     def forward(self, x):
#         x = self.features(x)
#         x = x.mean(3).mean(2)
#         x = self.classifier(x)
#         return x
#
#     def _initialize_weights(self):
#         for m in self.modules():
#             if isinstance(m, nn.Conv2d):
#                 n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
#                 m.weight.data.normal_(0, math.sqrt(2. / n))
#                 if m.bias is not None:
#                     m.bias.data.zero_()
#             elif isinstance(m, nn.BatchNorm2d):
#                 m.weight.data.fill_(1)
#                 m.bias.data.zero_()
#             elif isinstance(m, nn.Linear):
#                 n = m.weight.size(1)
#                 m.weight.data.normal_(0, 0.01)
#                 m.bias.data.zero_()
#
#
#     def mobilenet_v2(pretrained=True):
#         model = MobileNetV2(width_mult=1)
#
#         if pretrained:
#             try:
#                 from torch.hub import load_state_dict_from_url
#             except ImportError:
#                 from torch.utils.model_zoo import load_url as load_state_dict_from_url
#             state_dict = load_state_dict_from_url(
#                 'https://www.dropbox.com/s/47tyzpofuuyyv1b/mobilenetv2_1.0-f2a8633.pth.tar?dl=1', progress=True)
#             model.load_state_dict(state_dict)
#         return model
#
#     def fntest(self):
#         print('Test')
#
#
#
#
# # if __name__ == '__main__':
# #     net = MobileNetV2.mobilenet_v2(True)
# #     print(net)