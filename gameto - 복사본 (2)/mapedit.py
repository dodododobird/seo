import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from PIL import Image, ImageTk
import json
import os
import sys

class MapEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("맵 에디터")
        self.root.geometry("1200x800")
        
        # CustomTkinter 테마 설정
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # 변수 초기화
        self.map_image = None
        self.map_tk_image = None
        self.current_map_path = None
        self.current_map_name = None
        self.walkable_areas = []  # [x1, y1, x2, y2] 형식의 사각형 영역
        self.start_position = [100, 100]  # 기본 시작 위치
        
        # 영역 그리기 관련 변수
        self.drawing = False
        self.start_x = 0
        self.start_y = 0
        self.current_rect = None
        self.current_area_type = "walkable"  # "walkable" 또는 "unwalkable"
        
        # UI 설정
        self.setup_ui()
        
    def setup_ui(self):
        # 메인 프레임
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 왼쪽 패널 (도구 및 설정)
        self.left_panel = ctk.CTkFrame(self.main_frame, width=200)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # 오른쪽 패널 (맵 캔버스)
        self.right_panel = ctk.CTkFrame(self.main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 맵 캔버스
        self.canvas_frame = ctk.CTkFrame(self.right_panel)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 스크롤바
        self.h_scrollbar = ctk.CTkScrollbar(self.right_panel, orientation="horizontal", command=self.canvas.xview)
        self.h_scrollbar.pack(fill=tk.X)
        
        self.v_scrollbar = ctk.CTkScrollbar(self.right_panel, orientation="vertical", command=self.canvas.yview)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        
        # 왼쪽 패널 버튼
        self.load_button = ctk.CTkButton(self.left_panel, text="맵 이미지 로드", command=self.load_map)
        self.load_button.pack(fill=tk.X, padx=10, pady=10)
        
        self.save_button = ctk.CTkButton(self.left_panel, text="설정 저장", command=self.save_map_config)
        self.save_button.pack(fill=tk.X, padx=10, pady=10)
        
        # 영역 타입 선택
        self.area_label = ctk.CTkLabel(self.left_panel, text="영역 타입:")
        self.area_label.pack(padx=10, pady=(20, 5), anchor=tk.W)
        
        self.area_var = tk.StringVar(value="walkable")
        
        self.walkable_radio = ctk.CTkRadioButton(
            self.left_panel, text="이동 가능 영역",
            variable=self.area_var, value="walkable",
            command=self.change_area_type
        )
        self.walkable_radio.pack(padx=20, pady=5, anchor=tk.W)
        
        self.unwalkable_radio = ctk.CTkRadioButton(
            self.left_panel, text="이동 불가능 영역",
            variable=self.area_var, value="unwalkable",
            command=self.change_area_type
        )
        self.unwalkable_radio.pack(padx=20, pady=5, anchor=tk.W)
        
        # 현재 맵 정보 표시
        self.info_frame = ctk.CTkFrame(self.left_panel)
        self.info_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.map_name_label = ctk.CTkLabel(self.info_frame, text="맵 이름: 없음")
        self.map_name_label.pack(anchor=tk.W, padx=10, pady=5)
        
        self.area_count_label = ctk.CTkLabel(self.info_frame, text="영역 수: 0")
        self.area_count_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # 작업 버튼
        self.clear_areas_button = ctk.CTkButton(
            self.left_panel, text="모든 영역 지우기",
            command=self.clear_all_areas
        )
        self.clear_areas_button.pack(fill=tk.X, padx=10, pady=10)
        
        self.set_start_button = ctk.CTkButton(
            self.left_panel, text="시작 위치 설정",
            command=self.set_start_position
        )
        self.set_start_button.pack(fill=tk.X, padx=10, pady=10)
        
        # 캔버스 이벤트 바인딩
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # 도움말
        self.help_text = ctk.CTkTextbox(self.left_panel, height=200)
        self.help_text.pack(fill=tk.X, padx=10, pady=10)
        self.help_text.insert("1.0", "사용 방법:\n\n"
                           "1. 맵 이미지 로드를 클릭하여 맵 이미지를 선택합니다.\n\n"
                           "2. 이동 가능/불가능 영역을 선택한 후 드래그하여 영역을 그립니다.\n\n"
                           "3. 시작 위치 설정을 클릭하여 플레이어의 시작 위치를 지정합니다.\n\n"
                           "4. 설정 저장을 클릭하여 맵 설정을 저장합니다.")
        self.help_text.configure(state="disabled")
        
    def load_map(self):
        # 이미지 파일 선택
        file_path = filedialog.askopenfilename(
            title="맵 이미지 선택",
            filetypes=[("이미지 파일", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        
        if not file_path:
            return
            
        try:
            # 이미지 로드
            self.map_image = Image.open(file_path)
            self.map_tk_image = ImageTk.PhotoImage(self.map_image)
            
            # 맵 정보 업데이트
            self.current_map_path = file_path
            self.current_map_name = os.path.splitext(os.path.basename(file_path))[0]
            self.map_name_label.configure(text=f"맵 이름: {self.current_map_name}")
            
            # 캔버스 크기 설정
            width, height = self.map_image.size
            self.canvas.config(scrollregion=(0, 0, width, height))
            
            # 이미지 표시
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.map_tk_image, tags="map")
            
            # 이미 저장된 설정이 있는지 확인
            self.load_existing_config()
            
            messagebox.showinfo("성공", f"맵 이미지 '{self.current_map_name}'을(를) 로드했습니다.")
            
        except Exception as e:
            messagebox.showerror("오류", f"이미지 로드 중 오류가 발생했습니다: {e}")
            
    def load_existing_config(self):
        # maps 디렉토리 확인 및 생성
        os.makedirs("maps", exist_ok=True)
        
        # 설정 파일 경로
        config_path = f"maps/{self.current_map_name}_config.json"
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                self.walkable_areas = config.get("walkable_areas", [])
                self.start_position = config.get("start_position", [100, 100])
                
                # 영역 다시 그리기
                self.redraw_areas()
                # 시작 위치 다시 그리기
                self.draw_start_position()
                
                self.area_count_label.configure(text=f"영역 수: {len(self.walkable_areas)}")
                
                messagebox.showinfo("정보", "기존 맵 설정을 로드했습니다.")
                
            except Exception as e:
                messagebox.showwarning("경고", f"설정 파일 로드 중 오류 발생: {e}")
                
    def save_map_config(self):
        if not self.current_map_name:
            messagebox.showwarning("경고", "저장할 맵이 로드되지 않았습니다.")
            return
            
        try:
            # maps 디렉토리 확인 및 생성
            os.makedirs("maps", exist_ok=True)
            
            # 설정 파일 경로
            config_path = f"maps/{self.current_map_name}_config.json"
            
            # 설정 저장
            config = {
                "map_name": self.current_map_name,
                "walkable_areas": self.walkable_areas,
                "start_position": self.start_position
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            messagebox.showinfo("성공", f"맵 설정을 '{config_path}'에 저장했습니다.")
            
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 중 오류가 발생했습니다: {e}")
            
    def change_area_type(self):
        self.current_area_type = self.area_var.get()
        
    def clear_all_areas(self):
        if messagebox.askyesno("확인", "모든 영역을 지우시겠습니까?"):
            self.walkable_areas = []
            self.redraw_areas()
            self.area_count_label.configure(text="영역 수: 0")
            
    def set_start_position(self):
        if not self.current_map_name:
            messagebox.showwarning("경고", "맵이 로드되지 않았습니다.")
            return
            
        # 클릭 이벤트 핸들러 설정
        self.canvas.bind("<Button-1>", self.on_start_position_click)
        messagebox.showinfo("안내", "맵에서 시작 위치를 클릭하세요.")
        
    def on_start_position_click(self, event):
        # 시작 위치 저장
        self.start_position = [event.x, event.y]
        
        # 시작 위치 표시
        self.draw_start_position()
        
        # 이벤트 핸들러 복원
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        messagebox.showinfo("성공", f"시작 위치가 ({event.x}, {event.y})로 설정되었습니다.")
        
    def draw_start_position(self):
        # 기존 시작 위치 표시 제거
        self.canvas.delete("start_position")
        
        # 시작 위치 표시
        x, y = self.start_position
        self.canvas.create_oval(
            x-10, y-10, x+10, y+10,
            fill="blue", outline="white", width=2,
            tags="start_position"
        )
        self.canvas.create_text(
            x, y-20, text="시작 위치",
            fill="white", font=("맑은 고딕", 10, "bold"),
            tags="start_position"
        )
        
    def on_mouse_down(self, event):
        if not self.current_map_name:
            return
            
        self.drawing = True
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        
    def on_mouse_drag(self, event):
        if self.drawing:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            
            # 기존 임시 사각형 삭제
            if self.current_rect:
                self.canvas.delete(self.current_rect)
                
            # 새 임시 사각형 그리기
            fill_color = "green" if self.current_area_type == "walkable" else "red"
            self.current_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, canvas_x, canvas_y,
                outline="white", width=2, fill=fill_color, stipple="gray25", tags="temp_rect"
            )
            
    def on_mouse_up(self, event):
        if not self.drawing:
            return
            
        self.drawing = False
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # 임시 사각형 삭제
        if self.current_rect:
            self.canvas.delete(self.current_rect)
            self.current_rect = None
            
        # 영역 좌표 정규화 (x1 < x2, y1 < y2)
        x1 = min(self.start_x, canvas_x)
        y1 = min(self.start_y, canvas_y)
        x2 = max(self.start_x, canvas_x)
        y2 = max(self.start_y, canvas_y)
        
        # 영역이 너무 작으면 무시
        if x2 - x1 < 10 or y2 - y1 < 10:
            return
            
        # 영역 추가
        if self.current_area_type == "walkable":
            self.walkable_areas.append([int(x1), int(y1), int(x2), int(y2)])
            self.area_count_label.configure(text=f"영역 수: {len(self.walkable_areas)}")
            
        self.redraw_areas()
        
    def redraw_areas(self):
        # 모든 영역 삭제
        self.canvas.delete("area")
        
        # 이동 가능 영역 다시 그리기
        for i, area in enumerate(self.walkable_areas):
            x1, y1, x2, y2 = area
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="white", width=2, fill="green", stipple="gray25",
                tags=("area", f"area_{i}")
            )
            self.canvas.create_text(
                (x1 + x2) // 2, (y1 + y2) // 2,
                text=f"이동 가능 {i+1}",
                fill="white", font=("맑은 고딕", 10, "bold"),
                tags=("area", f"area_{i}")
            )

def main():
    root = ctk.CTk()
    app = MapEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main() 