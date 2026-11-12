def a():
    print('A 开始')
    raise ValueError('炸了')
    print('A 结束')          # ← 这行会执行吗？

def b():
    try:
        a()
    except ValueError:
        print('B 接住了')

b()
print('程序继续')