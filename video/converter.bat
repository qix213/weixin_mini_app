@echo off
if not exist "optimized_output" mkdir "optimized_output"

for %%i in (*.mp4) do (
    echo 正在处理优化视频: %%i ...
    :: -vf scale: 强制限制宽度为1280(720P)，高度自适应
    :: -crf 28: 增加压缩比（数值越高体积越小）
    :: -b:a 96k: 降低音频码率，手机听不出区别但能省空间
    ffmpeg -i "%%i" -vf "scale='min(1280,iw)':-2" -c:v libx264 -crf 28 -preset fast -c:a aac -b:a 96k -movflags +faststart "optimized_output\%%i"
)

echo ======= 处理完毕！输出文件夹：optimized_output =======
pause