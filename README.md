# 介绍

这是一个使用python脚本自动生成UEC++的dash文档的项目，

因为脚本使用的环境需要python2,但是一般人都只有python3,所以使用docker来启动

# 使用方法

在项目目录使用`start.sh`脚本,并在swap文件夹中放入引擎的文档压缩包

默认命名为`CppAPI-HTML.tgz`

```

sh ./start.sh

```

等项目跑完之后swap中会出现api的dash文档压缩包

脚本来自

https://imzlp.com/posts/11515/
