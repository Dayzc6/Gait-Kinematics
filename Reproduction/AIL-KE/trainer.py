# 主训练程序

import torch as t
import numpy as np
import pandas as pd
import torch.nn as nn

class MainTrain(nn.Module):
    def __init__(self):
        super().__init__()
        self.device=None
        if t.cuda.is_available(): 
	        self.device = t.device('cuda:0')
        # else: 
            # self.device = t.device('cpu')
        
    

        








# if __name__=="__main__":
    