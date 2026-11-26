# -*- coding: utf-8 -*-
"""skills/ 通用 Skill 组件层（架构第二层）。

承载可被应用层通用调用的原子化 Skill。每个 Skill 继承
skills.base.skill_base.BaseSkill，统一通过 ctx.gateway 取数。
"""
