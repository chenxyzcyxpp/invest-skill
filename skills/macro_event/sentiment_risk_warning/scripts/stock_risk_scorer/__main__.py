# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""支持 python -m stock_risk_scorer 直接运行。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_risk_scorer.cli import main

if __name__ == "__main__":
    main()
