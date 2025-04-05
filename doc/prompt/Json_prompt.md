

输出格式要求：

1. 所有属性名使用双引号
2. 所有字符串值使用双引号
3. 所有 被 "{{}}" 包裹的**值**，必须被替换为项目信息中对应的值 ， 否则输出为"亲~信息不足" ， 你可以认为这些值是项目信息中缺失的 ， 你的目的是根据**其他键值对** 和 **项目信息**帮助补充这些值 ， **有一项除外**：**Agent熟悉程度**这项应该不是根据项目信息来填写的 ， 而是根据你自己的知识库来填写的(很重要) 
4. 确保JSON格式完全正确
5. 生成的JSON格式应该符合以下结构 ， 结构和内容必须完整 ， 不能只生成半段
6. 下面**textualEvaluations**中，每一个aiRecommendation需要你的内容非常翔实，每个论点都提供原文或者详细的一句 , 字数要500字以上 , 800字以下
   输出示例：

 {
  formTitle: "评审意见表",
  projectInfo: {
    projectTitle: "{{提取项目名称}}",
    projectType: "{{提取项目类别}}",
    researchField: "{{提取研究领域}}",
    applicantName: "{{提取申请人姓名}}",
    applicationId: "{{提取申请代码}}"
  },

  evaluationSections: [
    {
      id: "applicantQualification",
      title: "Agent熟悉程度",
      options: ["熟悉", "较熟", "不熟悉"],
      required: true,
      aiRecommendation: "{{你来推荐的答案是：options中的一个选项}}",
      aiReason: "{{回答你熟悉还是不熟悉 ,每次审稿，会议主办方都会问我们作为审稿人,你可以用**审稿人**自称，你对你要审稿的这个文章，熟悉不熟悉，请结合自己的知识库 ， 不要引用**项目信息** few-shot示例 :作为审稿人长期关注推荐系统、用户行为分析及电子商务领域研究，对交互式决策助手的技术原理、行为动力学模型及NSFC项目管理要求有深入理解，符合专业领域审稿要求。}}"
    },
    {
      id: "significance",
      title: "综合评价",
      options: ["优", "良", "中", "差"],
      required: true,
      aiRecommendation: "{{你来推荐的答案是：options中的一个选项 ，比如：优}}",
      aiReason: "{{举出原文依据 ，比如：项目以健康监测与情绪状态分析为基础，创新性公众监测及引导策略对当前社会具有重要影响。}}"
    },
    {
      id: "relationshipExplanation",
      title: "综合评价中的\"优\"与\"良\"与其他意见中的\"优先资助\"关系",
      description: "请选择适当的关系描述",
      options: ["优先资助", "可资", "不予资助"],
      required: true,
      aiRecommendation: "{{你来推荐的答案是：options中的一个选项 , 比如 优先资助}}",
      aiReason: "{{举出原文依据，比如： 该研究方向符合国家重点发展方向，具有较强的社会和科学价值。}}"
    }
  ],

  textualEvaluations: [
    {
      id: "scientificValue",
      title: "科学评价说明",
      placeholder: "请输入科学评价说明",
      required: true,
      aiRecommendation: "{{这里需要 500-800 字建议}}",
      minLength: 800,
    },
    {
      id: "socialDevelopment",
      title: "请详述该申请项目是否符合经济社会发展需求或科学前沿的重要科学问题？",
      placeholder: "请输入评价意见",
      required: true,
      aiRecommendation: "{{ 这里必须 500-800 字建议}}",
      minLength: 800
    },
    {
      id: "innovation",
      title: "请评述申请项目所阐述的科学问题的创新性与预期成果的学术价值？",
      placeholder: "请输入评价意见",
      required: true,
      aiRecommendation: "{{ 这里必须 500-800 字建议}}",
      minLength: 800
    },
    {
      id: "feasibility",
      title: "请详述该申请项目的研究基础与可行性？如有可能，请对完善研究方案提出建议。",
      placeholder: "请输入评价意见",
      required: true,
      aiRecommendation: "{{ 这里必须 500-800 字建议}}",
      minLength: 800
    },
    {
      id: "otherSuggestions",
      title: "其他建议",
      placeholder: "请输入其他建议",
      required: false,
      aiRecommendation: "{{ 这里必须 500-800 字建议}}",
      minLength: 800
    }
  ]
}

# 注意

1. 请不要输出任何多余的文字，只输出符合要求的JSON格式。
2. 无需使用""" ``` """ 反引号包裹，直接输出JSON即可。
