from PIL import Image, ImageDraw
import os

# 이미지 폴더 확인
if not os.path.exists("images"):
    os.makedirs("images")

# 캐릭터 이미지 생성
img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 원 그리기 - 파란색 플레이어
draw.ellipse((5, 5, 45, 45), fill=(0, 100, 255, 255), outline=(255, 255, 255, 255), width=2)

# 얼굴 표현
draw.ellipse((15, 15, 25, 25), fill=(255, 255, 255, 255))  # 왼쪽 눈
draw.ellipse((30, 15, 40, 25), fill=(255, 255, 255, 255))  # 오른쪽 눈
draw.arc((15, 25, 35, 40), 0, 180, fill=(255, 255, 255, 255), width=2)  # 미소

# 저장
img.save("images/player.png")
print("플레이어 이미지가 생성되었습니다: images/player.png") 