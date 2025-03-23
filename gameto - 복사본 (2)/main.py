import google.generativeai as genai
import json
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
from io import BytesIO
import os
import datetime
import random
import time
import numpy as np
import re
from aichat.manager import AIManager
from data.student_registry import STUDENT_REGISTRY
import openai
from typing import Dict, List, Tuple
import pygame
import threading
import traceback


# 이미지 경로 상수
IMAGE_DIR = "images"
LOCATION_IMAGES = {
    "복도": os.path.join(IMAGE_DIR, "corridor.png"),
    "운동장": os.path.join(IMAGE_DIR, "playground.png"),
    "과학실": os.path.join(IMAGE_DIR, "science_room.png"),
    "도서관": os.path.join(IMAGE_DIR, "library.png"),
    "식당": os.path.join(IMAGE_DIR, "map", "cafeteria.png")
}

# 캐릭터 이미지 상수
PLAYER_IMAGE = os.path.join(IMAGE_DIR, "player.png")  # 플레이어 이미지 (필요시 추가)

# ------------------------------
# 1. AI 모델 관리 클래스
# ------------------------------
class AIModelManager:
    def __init__(self):
        self.api_keys = self.load_api_keys()
        self.current_key_index = 0
        self.configure_models()

    def load_api_keys(self):
        keys = []
        for i in range(1, 3):
            try:
                with open(f"API_{i}.txt", "r") as f:
                    key = f.read().strip()
                    if key: keys.append(key)
            except: pass
        if not keys:
            raise ValueError("API 키 파일을 확인해 주세요 (API_1.txt, API_2.txt)")
        return keys

    def configure_models(self):
        genai.configure(api_key=self.api_keys[self.current_key_index])
        self.text_model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05') # 모델 변경
        self.vision_model = genai.GenerativeModel('gemini-1.5-flash') # 이미지 모델 유지 (필요시 변경)

    def generate_text(self, prompt: str, retry_count=0) -> str:
        if not prompt:
            print("텍스트 생성 오류: 프롬프트가 비어 있습니다.")
            return "NPC가 응답할 수 없습니다."
        try:
            print(f"🔄 API 요청 시도 (키 #{self.current_key_index + 1})")
            response = self.text_model.generate_content(prompt)
            if response.text:
                print(f"✅ API 응답 성공 (키 #{self.current_key_index + 1})")
                return response.text
            else:
                raise Exception("응답에 텍스트가 없습니다.")
            
        except Exception as e:
            print(f"⚠️ API 오류 발생 (키 #{self.current_key_index + 1}): {e}")
            
            # API 키 교체 시도
            if retry_count < len(self.api_keys):
                print(f"🔄 API 키 교체 시도 ({retry_count + 1}/{len(self.api_keys)})")
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                print(f"🔑 API 키 #{self.current_key_index + 1}로 전환")
                genai.configure(api_key=self.api_keys[self.current_key_index])
                self.text_model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')
                time.sleep(1)  # 잠시 대기
                return self.generate_text(prompt, retry_count + 1)
            
            print("❌ 모든 API 키 시도 실패")
            return "NPC가 응답할 수 없습니다."


    def generate_image(self, prompt: str) -> bytes:
        try:
            response = self.vision_model.generate_content(
                contents=[genai.ImagePart(data=None, mime_type=None), genai.TextPart(text=prompt)]
            )
            if response._result.candidates and response._result.candidates[0].content.parts:
                image_part = response._result.candidates[0].content.parts[0]
                if hasattr(image_part, 'data'):
                    return image_part.data
                else:
                    print(f"이미지 생성 오류: 응답 Part에 'data' 필드가 없습니다. 응답 구조 변경되었을 수 있습니다.")
                    print(f"응답 객체 구조: {response._result.candidates[0].content.parts[0]}")
                    print(f"전체 응답 객체: {response}")
                    return None
            else:
                print(f"이미지 생성 오류: 응답에서 이미지 데이터를 찾을 수 없습니다. 후보자 또는 Part가 없습니다.")
                print(f"전체 응답 객체: {response}")
                return None
        except Exception as e:
            print(f"이미지 생성 오류: {e}")
            return None

# ------------------------------
# 2. 데이터 관리 클래스
# ------------------------------
class DataManager:
    def __init__(self):
        self.locations = {
            "복도": {"npcs": []},
            "운동장": {"npcs": []},
            "과학실": {"npcs": []},
            "도서관": {"npcs": []}
        }
        self.npc_info = {}
        self.npc_number_mapping = {
            "강현준": "1",
            "유지은": "2",
            "임지수": "3",
            "남도윤": "4",
            "박하린": "5"
        }
        self.DATA_DIR = "data"
        self.EMOTION_DIR = "emotion"
        self.load_data()
        self.initialize_emotion_files()
        self.randomly_assign_npcs_to_locations()

    def initialize_emotion_files(self):
        """게임 시작 시 감정 상태 초기화"""
        try:
            for npc_name, npc_number in self.npc_number_mapping.items():
                # data 폴더 경로 추가
                json_path = os.path.join(self.DATA_DIR, f"student_{npc_number}.json")
                emotion_path = os.path.join(self.EMOTION_DIR, f"emotion{npc_number}.txt")
                
                # student_*.json 파일에서 감정 상태 로드
                with open(json_path, 'r', encoding='utf-8') as f:
                    npc_data = json.load(f)
                    emotional_stats = npc_data['psychology']['emotional_stats']
                
                # emotion*.txt 파일에 저장
                os.makedirs(self.EMOTION_DIR, exist_ok=True)  # emotion 디렉토리 생성
                with open(emotion_path, 'w', encoding='utf-8') as f:
                    json.dump(emotional_stats, f, ensure_ascii=False, indent=2)
                print(f"✅ {npc_name}의 감정 상태 초기화 완료")
        except Exception as e:
            print(f"감정 상태 초기화 중 오류 발생: {e}")

    def get_npc_number(self, npc_name):
        """NPC 이름에 해당하는 번호 반환"""
        try:
            return self.npc_number_mapping.get(npc_name, "1")
        except Exception as e:
            print(f"❌ NPC 번호 조회 중 오류 발생: {e}")
            return "1"

    def get_npc_data(self, npc_name):
        """NPC 데이터 반환"""
        try:
            npc_number = self.get_npc_number(npc_name)
            if npc_number:
                # data 폴더 경로 추가
                file_path = os.path.join(self.DATA_DIR, f"student_{npc_number}.json")
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"NPC 데이터 로드 중 오류 발생: {e}")
        return None

    def load_data(self):
        """데이터 파일을 로드합니다."""
        try:
            data_file = os.path.join(self.DATA_DIR, "data.json")
            if os.path.exists(data_file):
                with open(data_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    # locations 데이터 업데이트 (기존 구조 유지)
                    loaded_locations = self.data.get("locations", {})
                    for loc in self.locations.keys():
                        if loc in loaded_locations:
                            self.locations[loc].update(loaded_locations[loc])
            else:
                print("data.json 파일이 없습니다. 기본 위치 정보를 사용합니다.")
                self.data = {"locations": self.locations}

            self.npcs = self.load_npcs()
            self.npc_data = {}
            self.all_npc_names = []
            
            # NPC 데이터 로드
            for i in range(1, 6):
                try:
                    json_path = os.path.join(self.DATA_DIR, f"student_{i}.json")
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data = self.validate_npc_data(data)
                        if data:
                            npc_name = data['name']
                            self.npc_data[npc_name] = data
                            self.all_npc_names.append(npc_name)
                except Exception as e:
                    print(f"⚠️ Error loading NPC data for student_{i}.json: {e}")

            self.randomly_assign_npcs_to_locations()

        except Exception as e:
            print(f"데이터 로드 중 오류 발생: {e}")

    def load_npcs(self):
        """NPC 정보를 로드합니다."""
        npcs = {}
        for npc_id, npc_data in self.data.get("npcs", {}).items():
            npcs[npc_id] = npc_data
        return npcs

    def load_emotion_prompt_template(self, filepath="emotion/makingemotion.txt"): # 감정 프롬프트 템플릿 로드 함수
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                template = f.read()
                print(f"😀 감정 변화 프롬프트 템플릿 로드 완료: {filepath}")
                return template
        except Exception as e:
            print(f"⚠️ 감정 변화 프롬프트 템플릿 로드 오류: {e}")
            return ""

    def load_emotion_prompt(self, filepath="emotion/makingemotion.txt"):
        """감정 변화 프롬프트 로드"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"감정 변화 프롬프트 로드 오류: {e}")
            return ""

    def load_emotion_values_from_files(self):
        """감정 파일에서 감정 수치 로드 또는 초기화"""
        for i, npc_name in enumerate(self.all_npc_names):
            emotion_file = f"emotion/emotion{i+1}.txt"
            initial_psychology = self.get_npc_base_psychology(npc_name).get('mental_health', {}) # 초기 심리 정보

            if os.path.exists(emotion_file):
                try:
                    with open(emotion_file, "r", encoding="utf-8") as f:
                        emotion_data = json.load(f)
                        if isinstance(emotion_data, dict): # dict type check
                            self.npc_data[npc_name]['psychology']['mental_health'] = emotion_data
                            print(f"😀 {npc_name} 감정 상태 '{emotion_file}' 파일에서 로드 완료: {emotion_data}")
                        else:
                            print(f"⚠️ {npc_name} 감정 파일 '{emotion_file}' 형식 오류, 초기화.")
                            self.npc_data[npc_name]['psychology']['mental_health'] = initial_psychology
                            self.save_emotion_values_to_files() # 초기화 후 저장
                except json.JSONDecodeError:
                    print(f"⚠️ {npc_name} 감정 파일 '{emotion_file}' JSON 디코드 오류, 초기화.")
                    self.npc_data[npc_name]['psychology']['mental_health'] = initial_psychology
                    self.save_emotion_values_to_files() # 초기화 후 저장

            else:
                print(f"🆕 {npc_name} 감정 파일 '{emotion_file}' 새로 생성 및 초기화.")
                self.npc_data[npc_name]['psychology']['mental_health'] = initial_psychology
                self.save_emotion_values_to_files() # 파일 생성 및 초기값 저장

    def save_emotion_values_to_files(self):
        """현재 감정 수치를 emotion 파일에 저장"""
        for i, npc_name in enumerate(self.all_npc_names):
            emotion_file = f"emotion/emotion{i+1}.txt"
            emotion_data = self.npc_data[npc_name]['psychology']['mental_health']
            try:
                with open(emotion_file, "w", encoding="utf-8") as f:
                    json.dump(emotion_data, f, ensure_ascii=False, indent=2)
                print(f("💾 {npc_name} 감정 상태 '{emotion_file}' 파일에 저장 완료: {emotion_data}"))
            except Exception as e:
                print(f"⚠️ {npc_name} 감정 파일 '{emotion_file}' 저장 오류: {e}")

    def reset_emotion_files(self):
        """게임 종료 시 감정 파일을 student json 파일의 초기값으로 초기화"""
        print("🔄 게임 종료: 감정 파일 초기화 시작...")
        for i, npc_name in enumerate(self.all_npc_names):
            emotion_file = f"emotion/emotion{i+1}.txt"
            initial_psychology = self.get_npc_base_psychology(npc_name).get('mental_health', {})
            try:
                with open(emotion_file, "w", encoding="utf-8") as f:
                    json.dump(initial_psychology, f, ensure_ascii=False, indent=2)
                print(f"🔄 {npc_name} 감정 상태 '{emotion_file}' 초기화 완료 (student json): {initial_psychology}")
            except Exception as e:
                print(f"⚠️ {npc_name} 감정 파일 '{emotion_file}' 초기화 오류: {e}")
        print("🔄 감정 파일 초기화 완료.")


    def randomly_assign_npcs_to_locations(self):
        """NPC들을 랜덤하게 위치에 할당"""
        try:
            # 모든 NPC 이름 목록
            all_npcs = list(self.npc_number_mapping.keys())
            # 모든 위치 목록
            locations = list(self.locations.keys())
            
            # 각 위치의 NPC 목록 초기화
            for location in self.locations:
                self.locations[location]["npcs"] = []
            
            # NPC들을 랜덤하게 위치에 할당
            for npc in all_npcs:
                random_location = random.choice(locations)
                self.locations[random_location]["npcs"].append(npc)
            
            print("NPC 위치 할당 완료:")
            for location, data in self.locations.items():
                print(f"{location}: {data['npcs']}")
                
        except Exception as e:
            print(f"NPC 할당 중 오류 발생: {e}")

    def validate_npc_data(self, data: Dict) -> Dict:
        required_keys = ['name', 'core_info', 'image_prompt_template', 'psychology']
        try:
            # 기본 필수 키 검사
            for key in required_keys:
                if key not in data:
                    raise ValueError(f"Missing '{key}' in NPC data for {data.get('name', 'Unknown')}")
            
            # core_info 내부에 persona가 있는지 검사
            if 'core_info' not in data:
                raise ValueError(f"Missing 'core_info' for {data.get('name', 'Unknown')}")
                
            if 'persona' not in data['core_info']:
                raise ValueError(f"Missing 'persona' in 'core_info' for {data.get('name', 'Unknown')}")
            
            # persona 형식 검사
            persona = data['core_info']['persona']
            if not isinstance(persona, dict):
                raise ValueError(f"'persona' is not a dictionary for {data.get('name', 'Unknown')}")
            
            # persona 내부 필수 항목 검사
            if 'personality_rules' not in persona:
                raise ValueError(f"Missing 'personality_rules' in 'persona' for {data.get('name', 'Unknown')}")
            
            if 'speech_style' not in persona:
                raise ValueError(f"Missing 'speech_style' in 'persona' for {data.get('name', 'Unknown')}")

            return data
        except (KeyError, ValueError) as e:
            print(f"⚠️ Error validating NPC data: {e}, Data: {data}")
            return {}  # Return an empty dictionary to prevent program crash

    def get_npc(self, npc_name: str) -> dict:
        """주어진 이름의 NPC 정보를 반환합니다."""
        return self.npcs.get(npc_name)

    def get_npc_base_psychology(self, name: str) -> Dict: # student json 파일의 psychology 정보 반환
        npc_data = self.npc_data.get(name, {})
        return npc_data.get('psychology', {})

    def get_location_npcs(self, location: str) -> list:
        """특정 위치의 NPC 목록 반환"""
        try:
            return self.locations.get(location, {}).get("npcs", [])
        except Exception as e:
            print(f"위치 NPC 목록 조회 중 오류 발생: {e}")
            return []

    def get_npc_psychology(self, npc_name: str) -> Dict: # 현재 감정 상태 반환 (파일 or 초기값)
        npc_data = self.get_npc(npc_name)
        return npc_data.get('psychology', {}).get('mental_health', {}) # mental_health 정보 바로 반환으로 수정


    def update_emotion_states(self, npc_name, emotion_response):
        """감정 상태 업데이트 및 저장"""
        try:
            # JSON 형식의 감정 상태 파싱
            if isinstance(emotion_response, str):
                data = json.loads(emotion_response)
            elif isinstance(emotion_response, dict):
                data = emotion_response
            else:
                print(f"❌ 감정 상태 형식 오류: {type(emotion_response)}")
                return None
                
            if "final_emotions" in data:  # 최종 감정 상태 확인
                final_emotions = data["final_emotions"]
                
                # NPC 번호 가져오기
                npc_number = self.get_npc_number(npc_name)
                
                # emotion*.txt 파일에 저장
                emotion_file = f"emotion/emotion{npc_number}.txt"
                
                # 디렉토리 확인 및 생성
                os.makedirs(os.path.dirname(emotion_file), exist_ok=True)
                
                # 감정 상태를 JSON 형식으로 저장
                with open(emotion_file, 'w', encoding='utf-8') as f:
                    json.dump(final_emotions, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 감정 상태 저장 완료: {emotion_file}")
                return final_emotions
                
            else:
                print("❌ 'final_emotions' 키를 찾을 수 없습니다.")
                return None
                
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 형식이 아닌 응답입니다: {e}")
        except Exception as e:
            print(f"❌ 감정 상태 저장 중 오류 발생: {e}")
            traceback.print_exc()
        
        return None

    def get_current_emotions(self, npc_name):
        """현재 감정 상태 로드"""
        try:
            # NPC 번호 확인
            npc_number = self.get_npc_number(npc_name)
            emotion_file = f"emotion/emotion{npc_number}.txt"

            try:
                # 파일에서 감정 상태 읽기
                with open(emotion_file, 'r', encoding='utf-8') as f:
                    emotions = json.load(f)
                    print(f"✅ 감정 상태 로드 완료: {emotion_file}")
                    return emotions
                    
            except FileNotFoundError:
                # 파일이 없는 경우 기본값 설정
                print(f"⚠️ 감정 상태 파일 없음, 기본값 사용: {emotion_file}")
                emotions = {
                    "trust": "50",
                    "intimacy": "50",
                    "respect": "50",
                    "hostility": "50",
                    "annoyance": "50",
                    "curiosity": "50",
                    "wariness": "50"
                }
                # 기본값을 파일에 저장
                with open(emotion_file, 'w', encoding='utf-8') as f:
                    json.dump(emotions, f, ensure_ascii=False, indent=2)
                return emotions
                
            except json.JSONDecodeError:
                # JSON 형식이 아닌 경우 기본값 설정
                print(f"⚠️ 감정 상태 파일 JSON 형식 오류, 기본값 사용: {emotion_file}")
                emotions = {
                    "trust": "50",
                    "intimacy": "50",
                    "respect": "50",
                    "hostility": "50",
                    "annoyance": "50",
                    "curiosity": "50",
                    "wariness": "50"
                }
                # 기본값을 파일에 저장
                with open(emotion_file, 'w', encoding='utf-8') as f:
                    json.dump(emotions, f, ensure_ascii=False, indent=2)
                return emotions

        except Exception as e:
            print(f"❌ 감정 상태 로드 중 오류 발생: {e}")
            traceback.print_exc()
            # 기본값 반환
            return {
                "trust": "50",
                "intimacy": "50",
                "respect": "50",
                "hostility": "50",
                "annoyance": "50",
                "curiosity": "50",
                "wariness": "50"
            }

    def load_dialogue_template(self):
        """대화 템플릿 로드"""
        try:
            # dialogue_template.txt 대신 dialogue.txt 사용
            template_file = "dialogue.txt"
            
            if os.path.exists(template_file):
                with open(template_file, 'r', encoding='utf-8') as f:
                    template = f.read()
                print(f"✅ 대화 템플릿 로드 완료: {template_file}")
                return template
            else:
                print(f"❌ 대화 템플릿 파일을 찾을 수 없음: {template_file}")
                return None
            
        except Exception as e:
            print(f"❌ 대화 템플릿 로드 중 오류 발생: {e}")
            return None

    def get_location_npcs_details(self, location: str) -> dict:
        """Returns a dictionary of NPC details for the given location."""
        location_data = self.locations.get(location)
        if location_data:
            return location_data.get("npcs", {})
        return {}

    def save_data(self):
        """데이터를 파일에 저장합니다."""
        try:
            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            print("데이터가 성공적으로 저장되었습니다.")
        except Exception as e:
            print(f"데이터 저장 중 오류 발생: {e}")

    def get_recent_conversation_history(self):
        """최근 대화 기록 반환"""
        return self.game_state.get("conversation_history", [])[-5:]  # 최근 5개 대화만 반환

    def calculate_relationship_level(self, emotions):
        """감정 상태를 기반으로 관계 레벨 계산"""
        if not emotions:
            return 50  # 기본값
        
        # 긍정적 감정들의 평균
        positive_emotions = ['trust', 'intimacy', 'respect']
        positive_values = [emotions.get(emotion, 50) for emotion in positive_emotions]
        positive_avg = sum(positive_values) / len(positive_values)
        
        # 부정적 감정들의 평균
        negative_emotions = ['hostility', 'annoyance']
        negative_values = [emotions.get(emotion, 0) for emotion in negative_emotions]
        negative_avg = sum(negative_values) / len(negative_values)
        
        # 최종 관계 레벨 계산
        relationship_level = positive_avg - negative_avg
        return max(0, min(100, relationship_level))  # 0~100 범위로 제한

    def analyze_and_update_emotions(self, npc_name, user_message, ai_response, inner_thoughts):
        """감정 상태 분석 및 업데이트"""
        try:
            # 현재 감정 상태 로드
            current_emotions = self.get_current_emotions(npc_name)
            if not current_emotions:
                print("❌ 현재 감정 상태를 불러올 수 없습니다.")
                return {}
                
            emotion_changes = {}
            
            # 감정 키워드 매핑
            emotion_keywords = {
                'trust': ['신뢰', '믿음', '의지'],
                'intimacy': ['친밀', '가까움', '친근'],
                'respect': ['존경', '존중', '인정'],
                'bond': ['유대', '연결', '공감'],
                'cooperation': ['협력', '협동', '도움'],
                'rivalry': ['경쟁', '대립', '견제'],
                'fellowship': ['동료애', '우정', '친구'],
                'mentoring': ['가르침', '지도', '조언'],
                'hostility': ['적대', '미움', '반감'],
                'betrayal': ['배신', '실망', '배반'],
                'resentment': ['분노', '화남', '격분'],
                'distrust': ['불신', '의심', '불안'],
                'envy': ['질투', '시기', '부러움'],
                'guilt': ['죄책감', '후회', '미안'],
                'admiration': ['감탄', '존경', '동경'],
                'loyalty': ['충성', '헌신', '충실'],
                'fear': ['두려움', '공포', '무서움'],
                'avoidance': ['회피', '도망', '기피'],
                'rejection': ['거절', '거부', '외면'],
                'curiosity': ['호기심', '궁금', '관심'],
                'confusion': ['혼란', '혼돈', '당황'],
                'annoyance': ['짜증', '불만', '성가심'],
                'wariness': ['경계', '조심', '주의'],
                'bewilderment': ['당황', '혼란', '놀람']
            }
            
            # 전체 응답 텍스트 (소문자로 변환)
            response_text = f"{user_message} {ai_response} {inner_thoughts}".lower()
            
            # 각 감정에 대해 변화 계산
            for emotion, keywords in emotion_keywords.items():
                if emotion in current_emotions:
                    try:
                        current_value = float(current_emotions[emotion])
                        change = 0
                        
                        # 키워드 검색 및 맥락 분석
                        for keyword in keywords:
                            if keyword in response_text:
                                # 긍정/부정 맥락 확인
                                positive_context = any(pos in response_text for pos in 
                                    ['좋아', '긍정', '기쁘', '행복', '만족', '즐거움', '감사'])
                                negative_context = any(neg in response_text for neg in 
                                    ['나쁘', '부정', '슬프', '화나', '실망', '불만', '싫어'])
                                
                                # 감정 강도 분석
                                intensity = 1.0
                                if any(intens in response_text for intens in ['매우', '정말', '너무', '굉장히']):
                                    intensity = 2.0
                                
                                # 맥락에 따른 변화량 결정
                                if positive_context:
                                    change += random.uniform(2.0, 5.0) * intensity
                                elif negative_context:
                                    change -= random.uniform(2.0, 5.0) * intensity
                                else:
                                    change += random.uniform(-2.0, 2.0) * intensity
                        
                        # 의미있는 변화만 처리 (변화량 임계값 낮춤)
                        if abs(change) > 0.5:
                            # 변화량 제한
                            change = max(min(change, 10.0), -10.0)
                            
                            # 새 값 계산 및 범위 제한
                            new_value = max(0, min(100, current_value + change))
                            
                            # 유의미한 변화가 있는 경우에만 기록
                            if abs(new_value - current_value) > 0.5:
                                # 변화 기록 (이전 값, 새 값)
                                emotion_changes[emotion] = (current_value, new_value)
                                
                                # 감정 상태 업데이트
                                current_emotions[emotion] = str(round(new_value, 1))
                    except ValueError:
                        print(f"❌ 감정 값 변환 오류: {emotion}={current_emotions[emotion]}")
                        continue
            
            # 변화가 있을 경우에만 저장
            if emotion_changes:
                # 감정 상태 JSON 형식으로 변환
                emotions_json = json.dumps({"final_emotions": current_emotions})
                
                # 감정 상태 업데이트 및 저장
                self.update_emotion_states(npc_name, emotions_json)
                print(f"✅ {npc_name}의 감정 변화 감지 및 저장: {len(emotion_changes)}개 감정 변화")
            
            return emotion_changes
            
        except Exception as e:
            print(f"❌ 감정 분석 중 오류 발생: {e}")
            traceback.print_exc()  # 자세한 오류 출력
            return {}

# ------------------------------
# 3. 메인 게임 클래스
# ------------------------------
class GameWindow:
    def __init__(self, root):
        """초기화"""
        try:
            self.root = root
            self.root.title("좀비 아포칼립스 RPG")

            # CustomTkinter 테마 설정
            ctk.set_appearance_mode("dark")  # 다크 모드
            ctk.set_default_color_theme("blue")  # 블루 테마
            
            # 디렉토리 경로 설정
            self.IMAGE_DIR = "images"
            self.MUSIC_DIR = "music"
            
            # pygame 초기화
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
                print("✅ pygame 믹서 초기화 성공")
            except Exception as e:
                print(f"❌ pygame 믹서 초기화 실패: {e}")
            
            # 현재 재생 중인 음악 트랙 저장용
            self.current_music = None
            
            # 2D 맵 관련 속성
            self.map_window = None  # 맵 창 참조
            self.map_canvas = None  # 맵 캔버스
            self.player_pos = [100, 100]  # 플레이어 초기 위치
            self.map_size = (800, 600)  # 맵 크기
            self.player_size = (30, 30)  # 플레이어 크기
            self.npc_positions = {}  # NPC 위치 저장 딕셔너리
            self.current_map = "식당"  # 현재 맵
            self.walkable_areas = []  # 이동 가능 영역
            self.map_loaded = False  # 맵 로드 여부
            
            # 감정 이름 매핑 설정
            self.emotion_names = {
                'trust': '신뢰',
                'intimacy': '친밀감',
                'respect': '존경',
                'bond': '유대감',
                'cooperation': '협력',
                'rivalry': '경쟁심',
                'fellowship': '동료애',
                'mentoring': '멘토링',
                'hostility': '적대감',
                'betrayal': '배신감',
                'resentment': '원한',
                'distrust': '불신',
                'envy': '질투',
                'guilt': '죄책감',
                'admiration': '감탄',
                'loyalty': '충성심',
                'authority': '권위',
                'leadership': '리더십',
                'love': '사랑',
                'romantic': '로맨틱',
                'passion': '열정',
                'possessiveness': '소유욕',
                'protective': '보호',
                'dependency': '의존성',
                'responsibility': '책임감',
                'devotion': '헌신',
                'fear': '공포',
                'avoidance': '회피',
                'rejection': '거부',
                'inferiority': '열등감',
                'intimidation': '위협',
                'superiority': '우월감',
                'familiarity': '친숙함',
                'curiosity': '호기심',
                'confusion': '혼란',
                'annoyance': '짜증',
                'awkwardness': '어색함',
                'discomfort': '불편함',
                'wariness': '경계심',
                'bewilderment': '당황'
            }
            
            # 위치별 이미지 경로 설정
            self.LOCATION_IMAGES = {
                "운동장": f"{self.IMAGE_DIR}/playground.png",
                "과학실": f"{self.IMAGE_DIR}/science_room.png",
                "도서관": f"{self.IMAGE_DIR}/library.png",
                "복도": f"{self.IMAGE_DIR}/corridor.png"
            }
            
            # 위치별 음악 파일 경로 설정
            self.LOCATION_MUSIC = {
                "운동장": f"{self.MUSIC_DIR}/music1.mp3",
                "과학실": f"{self.MUSIC_DIR}/music2.mp3",
                "도서관": f"{self.MUSIC_DIR}/music1.mp3",
                "복도": f"{self.MUSIC_DIR}/music2.mp3"
            }
            
            # NPC 번호 매핑
            self.npc_numbers = {
                "강현준": "1",
                "임지수": "2",
                "남도윤": "3",
                "박하린": "4",
                "유지은": "5"
            }
            
            # 게임 상태 초기화
            self.game_state = {
                "current_location": "복도",
                "selected_npc": None,
                "conversation_history": [],
                "current_emotions": {},
                "npcs_by_location": {
                    "운동장": ["임지수", "박하린"],
                    "과학실": ["강현준", "남도윤"],
                    "도서관": ["유지은"],
                    "복도": []
                }
            }
            
            # AI 모델 매니저 초기화
            self.ai_model = AIModelManager()
            
            # DataManager 인스턴스 생성
            self.data_manager = DataManager()
            
            # UI 컴포넌트 초기화
            self.main_frame = None
            self.left_frame = None
            self.center_frame = None
            self.right_frame = None
            self.location_label = None
            self.location_image_label = None
            self.npc_list_frame = None
            self.npc_buttons = {}
            self.conversation_text = None
            self.input_frame = None
            self.message_entry = None
            
            # UI 설정
            self.setup_ui()
            
        except Exception as e:
            print(f"❌ 게임 초기화 중 오류 발생: {e}")

    def setup_ui(self):
        """UI 설정"""
        try:
            # 메인 프레임 생성
            self.main_frame = ctk.CTkFrame(self.root)
            self.main_frame.pack(expand=True, fill='both', padx=20, pady=20)
            
            # 왼쪽 프레임 생성
            self.left_frame = ctk.CTkFrame(self.main_frame)
            self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
            
            # 중앙 프레임 생성
            self.center_frame = ctk.CTkFrame(self.main_frame)
            self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 오른쪽 프레임 생성
            self.right_frame = ctk.CTkFrame(self.main_frame)
            self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
            
            # 각 프레임 설정
            self.setup_left_frame()
            self.setup_center_frame()
            self.setup_right_frame()
            
            # 2D 맵 창 초기화
            self.init_map_window()
            
        except Exception as e:
            print(f"❌ UI 설정 중 오류 발생: {e}")
            
    def init_map_window(self):
        """2D 맵 창 초기화"""
        try:
            # 맵 창 생성
            self.map_window = ctk.CTkToplevel(self.root)
            self.map_window.title("2D 맵 - " + self.current_map)
            self.map_window.geometry(f"{self.map_size[0]}x{self.map_size[1]}+{self.root.winfo_x() + self.root.winfo_width() + 10}+{self.root.winfo_y()}")
            self.map_window.protocol("WM_DELETE_WINDOW", lambda: self.map_window.withdraw())  # 닫기 버튼 처리
            
            # 맵 창 캔버스 생성
            self.map_canvas = tk.Canvas(self.map_window, width=self.map_size[0], height=self.map_size[1], bg="black")
            self.map_canvas.pack(fill=tk.BOTH, expand=True)
            
            # 맵 로드
            self.load_map(self.current_map)
            
            # 키 이벤트 바인딩
            self.map_window.bind("<KeyPress>", self.handle_key_press)
            self.map_window.focus_set()  # 포커스 설정
            
            # 맵 업데이트 타이머 설정
            self.update_map()
            
        except Exception as e:
            print(f"❌ 맵 창 초기화 중 오류 발생: {e}")
            traceback.print_exc()
            
    def load_map(self, map_name):
        """맵 로드"""
        try:
            # 맵 이미지 로드
            map_path = LOCATION_IMAGES.get(map_name)
            if not map_path or not os.path.exists(map_path):
                print(f"❌ 맵 이미지를 찾을 수 없습니다: {map_path}")
                return
                
            # 맵 이미지 로드 및 크기 조정
            map_img = Image.open(map_path)
            map_img = map_img.resize(self.map_size, Image.LANCZOS)
            self.map_image = ImageTk.PhotoImage(map_img)
            
            # 맵 이미지 표시
            self.map_canvas.create_image(0, 0, anchor="nw", image=self.map_image)
            
            # 문을 찾아서 표시 - 나중에 구현
            
            # 이동 가능 영역 로드
            self.load_walkable_areas(map_name)
            
            # NPC 위치 랜덤 배치
            self.place_npcs_randomly()
            
            # 맵 로드 완료
            self.map_loaded = True
            self.current_map = map_name
            self.map_window.title("2D 맵 - " + map_name)
            
        except Exception as e:
            print(f"❌ 맵 로드 중 오류 발생: {e}")
            traceback.print_exc()

    def setup_left_frame(self):
        """왼쪽 프레임 설정"""
        try:
            # 왼쪽 프레임 크기 조정 (이미지 크기에 맞춤)
            frame_width = 220  # 이미지 크기 + 여백
            self.left_frame.configure(width=frame_width)
            
            # 현재 위치 표시 레이블
            self.location_label = ctk.CTkLabel(
                self.left_frame, 
                text=f"현재 위치: {self.game_state['current_location']}",
                font=("Helvetica", 16, "bold")
            )
            self.location_label.pack(side=tk.TOP, pady=10)
            
            # 위치 이미지 표시 프레임
            img_frame = ctk.CTkFrame(self.left_frame)
            img_frame.pack(side=tk.TOP, pady=10)
            
            self.location_image_label = ctk.CTkLabel(img_frame, text="")
            self.location_image_label.pack(side=tk.TOP, pady=10)
            
            # 위치 선택 버튼들 프레임
            locations_frame = ctk.CTkFrame(self.left_frame)
            locations_frame.pack(fill=tk.X, padx=10, pady=10)
            
            locations_label = ctk.CTkLabel(
                locations_frame, 
                text="이동 가능 위치",
                font=("Helvetica", 14, "bold")
            )
            locations_label.pack(pady=(5, 10))
            
            locations = ["복도", "과학실", "도서관", "운동장"]
            for location in locations:
                btn = ctk.CTkButton(
                    locations_frame,
                    text=location,
                    command=lambda loc=location: self.change_location(loc),
                    font=("Helvetica", 12),
                    corner_radius=10,
                    hover_color="#2A8C55",
                    fg_color="#2B6747"
                )
                btn.pack(fill=tk.X, padx=10, pady=5)
            
            # NPC 목록 프레임
            npc_frame = ctk.CTkFrame(self.left_frame)
            npc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            npc_label = ctk.CTkLabel(
                npc_frame, 
                text="NPC 목록",
                font=("Helvetica", 14, "bold")
            )
            npc_label.pack(side=tk.TOP, pady=10)
            
            # 스크롤 가능한 NPC 목록 프레임
            self.npc_list_frame = ctk.CTkScrollableFrame(npc_frame)
            self.npc_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # NPC 목록 초기화
            self.update_npc_list()
            
        except Exception as e:
            print(f"❌ 왼쪽 프레임 설정 중 오류 발생: {e}")

    def update_npc_list(self):
        """NPC 목록 업데이트"""
        try:
            # 기존 NPC 버튼들 제거
            for widget in self.npc_list_frame.winfo_children():
                widget.destroy()
            
            # 현재 위치의 NPC 목록 가져오기
            current_location = self.game_state["current_location"]
            npcs = self.game_state["npcs_by_location"].get(current_location, [])
            
            # NPC 없을 경우 메시지 표시
            if not npcs:
                empty_label = ctk.CTkLabel(
                    self.npc_list_frame, 
                    text="이 위치에 NPC가 없습니다",
                    text_color="gray"
                )
                empty_label.pack(pady=20)
                return
            
            # NPC 버튼 생성
            for npc in npcs:
                npc_frame = ctk.CTkFrame(self.npc_list_frame)
                npc_frame.pack(fill=tk.X, padx=5, pady=5, ipadx=5, ipady=5)
                
                # NPC 이미지 로드 및 표시
                try:
                    npc_number = self.get_npc_number(npc)
                    image_path = f"images/{npc_number}.png"
                    photo = self.load_npc_image(image_path, max_size=(80, 80))
                    
                    if photo:
                        image_label = ctk.CTkLabel(npc_frame, image=photo, text="")
                        image_label.image = photo
                        image_label.pack(side=tk.LEFT, padx=5)
                    
                except Exception as e:
                    print(f"❌ NPC 이미지 로드 중 오류 발생: {e}")
                
                # NPC 버튼 
                button = ctk.CTkButton(
                    npc_frame,
                    text=npc,
                    command=lambda n=npc: self.select_npc(n),
                    font=("Helvetica", 12),
                    corner_radius=10,
                    hover_color="#6A64B5",
                    fg_color="#4B49AC"
                )
                button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
                self.npc_buttons[npc] = button
                
        except Exception as e:
            print(f"❌ NPC 목록 업데이트 중 오류 발생: {e}")

    def setup_center_frame(self):
        """중앙 프레임 설정"""
        # 대화창 제목
        conversation_header = ctk.CTkFrame(self.center_frame)
        conversation_header.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        conversation_label = ctk.CTkLabel(
            conversation_header, 
            text="대화", 
            font=("Helvetica", 16, "bold")
        )
        conversation_label.pack(pady=5)
        
        # 대화창
        self.conversation_frame = ctk.CTkFrame(self.center_frame)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.conversation_text = ctk.CTkTextbox(
            self.conversation_frame, 
            wrap="word", 
            font=("Malgun Gothic", 12),
            corner_radius=10
        )
        self.conversation_text.pack(expand=True, fill='both', padx=10, pady=10)
        
        # 입력 프레임
        self.input_frame = ctk.CTkFrame(self.center_frame)
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 입력창
        self.message_entry = ctk.CTkEntry(
            self.input_frame,
            font=("Malgun Gothic", 12),
            placeholder_text="메시지를 입력하세요...",
            height=40,
            corner_radius=10
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.message_entry.bind("<Return>", self.send_message_wrapper)
        
        # 전송 버튼
        self.send_button = ctk.CTkButton(
            self.input_frame, 
            text="전송", 
            command=self.send_message,
            font=("Helvetica", 12, "bold"),
            width=80,
            height=40,
            corner_radius=10,
            hover_color="#0E86D4",
            fg_color="#0063B2"
        )
        self.send_button.pack(side=tk.RIGHT)

    def setup_right_frame(self):
        """오른쪽 프레임 설정"""
        # 감정 상태 제목
        emotion_header = ctk.CTkFrame(self.right_frame)
        emotion_header.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        emotion_label = ctk.CTkLabel(
            emotion_header, 
            text="감정 상태", 
            font=("Helvetica", 16, "bold")
        )
        emotion_label.pack(pady=5)
        
        # 감정 상태 표시 영역
        self.emotion_frame = ctk.CTkFrame(self.right_frame)
        self.emotion_frame.pack(fill=tk.BOTH, padx=10, pady=10)
        
        # 감정 텍스트 위젯
        self.emotion_text = ctk.CTkTextbox(
            self.emotion_frame, 
            height=150, 
            width=250,
            font=("Malgun Gothic", 12),
            corner_radius=10
        )
        self.emotion_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 감정 변화 제목
        emotion_change_header = ctk.CTkFrame(self.right_frame)
        emotion_change_header.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        emotion_change_label = ctk.CTkLabel(
            emotion_change_header, 
            text="감정 변화", 
            font=("Helvetica", 16, "bold")
        )
        emotion_change_label.pack(pady=5)
        
        # 감정 변화 표시 영역
        self.emotion_change_frame = ctk.CTkFrame(self.right_frame)
        self.emotion_change_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 감정 변화 텍스트 위젯
        self.emotion_change_text = ctk.CTkTextbox(
            self.emotion_change_frame,
            height=120,
            font=("Malgun Gothic", 12),
            corner_radius=10
        )
        self.emotion_change_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 음악 설정 제목
        music_header = ctk.CTkFrame(self.right_frame)
        music_header.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        music_label = ctk.CTkLabel(
            music_header, 
            text="음악 설정", 
            font=("Helvetica", 16, "bold")
        )
        music_label.pack(pady=5)
        
        # 음악 컨트롤 프레임 추가
        music_control_frame = ctk.CTkFrame(self.right_frame)
        music_control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 볼륨 레이블
        volume_label = ctk.CTkLabel(
            music_control_frame, 
            text="볼륨:",
            font=("Helvetica", 12)
        )
        volume_label.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 볼륨 슬라이더
        self.volume_slider = ctk.CTkSlider(
            music_control_frame, 
            from_=0, 
            to=100, 
            orientation='horizontal',
            width=150,
            number_of_steps=20
        )
        self.volume_slider.set(100)  # 기본값 100%
        self.volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)
        self.volume_slider.configure(command=self.set_volume)
        
        # 볼륨 수치 표시
        self.volume_value_label = ctk.CTkLabel(
            music_control_frame, 
            text="100%",
            font=("Helvetica", 12)
        )
        self.volume_value_label.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 음소거 버튼
        self.mute_button = ctk.CTkButton(
            music_control_frame, 
            text="음소거", 
            command=self.toggle_mute,
            font=("Helvetica", 12),
            width=80,
            height=30,
            corner_radius=10,
            hover_color="#A36B7F",
            fg_color="#774360"
        )
        self.mute_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 음소거 상태 저장 변수
        self.is_muted = False
        self.prev_volume = 100
        
        # 버튼 프레임
        self.button_frame = ctk.CTkFrame(self.right_frame)
        self.button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 이동 버튼
        self.move_button = ctk.CTkButton(
            self.button_frame, 
            text="이동하기", 
            command=self.move_location,
            font=("Helvetica", 14, "bold"),
            height=40,
            corner_radius=10,
            hover_color="#B25D44",
            fg_color="#964B00"
        )
        self.move_button.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # 종료 버튼
        self.quit_button = ctk.CTkButton(
            self.button_frame, 
            text="종료", 
            command=self.quit_game,
            font=("Helvetica", 14, "bold"),
            height=40,
            corner_radius=10,
            hover_color="#C1464B",
            fg_color="#990F02"
        )
        self.quit_button.pack(side=tk.RIGHT, padx=10, fill=tk.X, expand=True)

    def set_volume(self, value):
        """볼륨 설정"""
        try:
            volume = int(float(value))
            # 볼륨 값 레이블 업데이트
            self.volume_value_label.config(text=f"{volume}%")
            
            # pygame 볼륨 설정 (0.0 ~ 1.0 사이 값으로 변환)
            normalized_volume = volume / 100.0
            pygame.mixer.music.set_volume(normalized_volume)
            
            # 음소거 상태 업데이트
            if volume > 0 and self.is_muted:
                self.is_muted = False
                self.mute_button.config(text="음소거")
            elif volume == 0 and not self.is_muted:
                self.is_muted = True
                self.mute_button.config(text="음소거 해제")
                
            # 이전 볼륨 값 저장 (0이 아닌 경우)
            if volume > 0:
                self.prev_volume = volume
                
        except Exception as e:
            print(f"❌ 볼륨 설정 중 오류 발생: {e}")

    def toggle_mute(self):
        """음소거 토글"""
        try:
            if self.is_muted:
                # 음소거 해제
                self.is_muted = False
                self.mute_button.config(text="음소거")
                self.volume_slider.set(self.prev_volume)
                pygame.mixer.music.set_volume(self.prev_volume / 100.0)
                self.volume_value_label.config(text=f"{self.prev_volume}%")
            else:
                # 음소거 적용
                self.is_muted = True
                self.mute_button.config(text="음소거 해제")
                # 현재 볼륨 저장
                self.prev_volume = int(self.volume_slider.get())
                # 볼륨 0으로 설정
                self.volume_slider.set(0)
                pygame.mixer.music.set_volume(0.0)
                self.volume_value_label.config(text="0%")
        except Exception as e:
            print(f"❌ 음소거 전환 중 오류 발생: {e}")

    def select_npc(self, npc_name):
        """NPC 선택 처리"""
        try:
            self.game_state["selected_npc"] = npc_name
            print(f"✅ NPC 선택됨: {npc_name}")
            
            # NPC 감정 상태 초기화
            if npc_name not in self.game_state["current_emotions"]:
                self.game_state["current_emotions"][npc_name] = {
                    "친밀도": 50,
                    "신뢰도": 50,
                    "호감도": 50,
                    "공포도": 50,
                    "분노": 50
                }
            
            # 대화 기록 초기화
            self.game_state["conversation_history"] = []
            
            # 대화창 초기화
            if hasattr(self, 'conversation_text'):
                self.conversation_text.delete(1.0, tk.END)
                self.conversation_text.insert(tk.END, f"=== {npc_name}과(와)의 대화 시작 ===\n\n")
            
            # 감정 상태 패널 업데이트
            self.update_emotion_panel()
            
        except Exception as e:
            print(f"❌ NPC 선택 중 오류 발생: {e}")

    def get_npc_number(self, npc_name):
        """NPC 이름에 해당하는 번호 반환"""
        try:
            return self.npc_numbers.get(npc_name, "1")
        except Exception as e:
            print(f"❌ NPC 번호 조회 중 오류 발생: {e}")
            return "1"

    def update_emotion_panel(self):
        """감정 상태 패널 업데이트"""
        try:
            selected_npc = self.game_state.get("selected_npc")
            if not selected_npc:
                return
            
            # 감정 텍스트 위젯 초기화
            self.emotion_text.configure(state='normal')
            self.emotion_text.delete('1.0', 'end')
            
            # 현재 감정 상태 로드
            current_emotions = self.data_manager.get_current_emotions(selected_npc)
            
            # 제목 추가
            self.emotion_text.insert('end', f"{selected_npc}의 감정 상태\n\n", ('title',))
            self.emotion_text._textbox.tag_configure('title', font=("Malgun Gothic", 14, "bold"))
            
            # 감정 상태 표시
            for emotion, value in current_emotions.items():
                if emotion in self.emotion_names:
                    emotion_kr = self.emotion_names[emotion]
                    try:
                        value_float = float(value)
                        
                        # 감정 수치에 따른 색상 결정
                        if value_float >= 80:
                            tag_name = f'emotion_high_{emotion}'
                            self.emotion_text._textbox.tag_configure(tag_name, foreground='#FF5555')
                        elif value_float >= 60:
                            tag_name = f'emotion_medium_{emotion}'
                            self.emotion_text._textbox.tag_configure(tag_name, foreground='#FFA500')
                        elif value_float <= 20:
                            tag_name = f'emotion_low_{emotion}'
                            self.emotion_text._textbox.tag_configure(tag_name, foreground='#5555FF')
                        else:
                            tag_name = f'emotion_normal_{emotion}'
                            self.emotion_text._textbox.tag_configure(tag_name, foreground='#FFFFFF')
                        
                        # 프로그레스 바 생성
                        bar_length = int(value_float / 5)  # 20단계로 나누기
                        bar = "█" * bar_length + "░" * (20 - bar_length)
                        
                        # 감정 이름 삽입
                        self.emotion_text.insert('end', f"{emotion_kr}: ", (f'emotion_label_{emotion}',))
                        self.emotion_text._textbox.tag_configure(f'emotion_label_{emotion}', font=("Malgun Gothic", 12, "bold"))
                        
                        # 프로그레스 바와 수치 삽입
                        self.emotion_text.insert('end', f"{bar} {value}%\n\n", (tag_name,))
                        
                    except ValueError:
                        continue
                    
            self.emotion_text.configure(state='disabled')
            
        except Exception as e:
            print(f"❌ 감정 패널 업데이트 중 오류 발생: {e}")

    def update_location_image(self, location):
        """위치 이미지 업데이트 (크기 2배 증가)"""
        try:
            if location in self.LOCATION_IMAGES:
                image_path = self.LOCATION_IMAGES[location]
                if os.path.exists(image_path):
                    # 이미지 크기를 (200, 200)으로 2배 증가
                    photo = self.load_npc_image(image_path, max_size=(200, 200))
                    if photo:
                        self.location_image_label.configure(image=photo)
                        self.location_image_label.image = photo
                else:
                    print(f"⚠️ 위치 이미지를 찾을 수 없습니다: {image_path}")
        except Exception as e:
            print(f"❌ 이미지 업데이트 중 오류 발생: {e}")

    def move_location(self):
        """새로운 위치로 이동"""
        try:
            # 이동 창 생성
            location_window = ctk.CTkToplevel(self.root)
            location_window.title("이동할 위치 선택")
            location_window.geometry("400x300")
            
            # 창을 화면 중앙에 위치
            window_width = 400
            window_height = 300
            screen_width = location_window.winfo_screenwidth()
            screen_height = location_window.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            location_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 제목 레이블
            title_label = ctk.CTkLabel(
                location_window,
                text="이동할 장소를 선택하세요",
                font=("Malgun Gothic", 18, "bold")
            )
            title_label.pack(pady=20)
            
            # 버튼 프레임
            button_frame = ctk.CTkFrame(location_window)
            button_frame.pack(expand=True, fill='both', padx=20, pady=10)
            
            # 그리드 구성
            locations = ["복도", "운동장", "과학실", "도서관"]
            current_location = self.game_state["current_location"]
            
            for i, location in enumerate(locations):
                row = i // 2
                col = i % 2
                
                # 버튼 스타일 설정
                button = ctk.CTkButton(
                    button_frame,
                    text=location,
                    command=lambda l=location: self.handle_location_selection(l, location_window),
                    font=('Malgun Gothic', 14),
                    width=120,
                    height=60,
                    corner_radius=10,
                    hover_color="#4F8A8B",
                    fg_color="#4C6663" if location != current_location else "#7A7A7A"
                )
                
                # 현재 위치면 비활성화
                if location == current_location:
                    button.configure(state="disabled")
                
                button.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            
            # 그리드 가중치 설정
            for i in range(2):
                button_frame.grid_rowconfigure(i, weight=1)
                button_frame.grid_columnconfigure(i, weight=1)
            
            # 취소 버튼
            cancel_button = ctk.CTkButton(
                location_window,
                text="취소",
                command=location_window.destroy,
                font=('Malgun Gothic', 14),
                width=100,
                height=40,
                corner_radius=10,
                hover_color="#C1464B",
                fg_color="#990F02"
            )
            cancel_button.pack(pady=20)

            # 모달 설정
            location_window.transient(self.root)
            location_window.grab_set()
            
        except Exception as e:
            print(f"위치 이동 창 생성 중 오류 발생: {e}")
            self.update_conversation("위치 이동 창을 생성할 수 없습니다.", "system")

    def handle_location_selection(self, new_location, window):
        """위치 선택 처리"""
        try:
            if new_location == self.game_state["current_location"]:
                self.update_conversation("이미 해당 위치에 있습니다.", "system")
                return
            
            # 이전 위치
            old_location = self.game_state["current_location"]
            
            # 위치 업데이트
            self.game_state["current_location"] = new_location
            self.location_label.config(text=f"현재 위치: {new_location}")
            
            # 이미지 업데이트
            self.update_images(location=new_location)
            
            # NPC 목록 업데이트
            self.update_npc_list()
            
            # 배경음악 변경
            self.play_location_music(new_location)
            
            # 메시지 표시
            self.update_conversation(f"{old_location}에서 {new_location}으로 이동했습니다.", "system")
            
            # 창 닫기
            window.destroy()
            
            # 선택된 NPC 초기화
            self.game_state["selected_npc"] = None
            if self.location_image_label:
                self.location_image_label.configure(image='')
            
            # 감정 패널 초기화 (빈 문자열 전달)
            self.update_emotion_panel()
            
            # 감정 변화 패널 초기화
            self.update_emotion_change_panel("", {})
            
        except Exception as e:
            print(f"위치 선택 처리 중 오류 발생: {e}")
            self.update_conversation("위치 선택 처리 중 오류가 발생했습니다.", "system")

    def update_images(self, npc_name=None, location=None):
        """이미지 업데이트"""
        try:
            if location:
                # 위치 이미지 업데이트
                image_path = self.LOCATION_IMAGES.get(location)
                if image_path and os.path.exists(image_path):
                    # 위치 이미지 크기 증가
                    photo = self.load_npc_image(image_path, max_size=(200, 200))
                    if photo:
                        self.location_image_label.configure(image=photo)
                        self.location_image_label.image = photo
                else:
                    print(f"⚠️ 위치 이미지를 찾을 수 없습니다: {image_path}")
            
            if npc_name:
                # NPC 이미지 업데이트
                npc_number = self.get_npc_number(npc_name)
                if npc_number:
                    npc_image_path = os.path.join(self.IMAGE_DIR, f"{npc_number}.png")
                    if os.path.exists(npc_image_path):
                        # NPC 이미지 크기도 증가
                        photo = self.load_npc_image(npc_image_path, max_size=(150, 150))
                        if photo:
                            self.location_image_label.configure(image=photo)
                            self.location_image_label.image = photo
                    else:
                        print(f"NPC 이미지를 찾을 수 없습니다: {npc_image_path}")

        except Exception as e:
            print(f"이미지 업데이트 중 오류 발생: {e}")

    def load_npc_image(self, image_path, max_size=(100, 100)):
        """NPC 이미지 로드 (비율 유지)"""
        try:
            if os.path.exists(image_path):
                image = Image.open(image_path)
                
                # 원본 비율 유지하면서 크기 조정
                width, height = image.size
                ratio = min(max_size[0]/width, max_size[1]/height)
                new_size = (int(width*ratio), int(height*ratio))
                
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                # CustomTkinter의 CTkImage 사용
                return ctk.CTkImage(light_image=image, dark_image=image, size=new_size)
            return None
        except Exception as e:
            print(f"❌ 이미지 로드 중 오류 발생: {e}")
            return None

    def send_message_wrapper(self, event=None):
        """메시지 전송 wrapper"""
        self.send_message()

    def send_message(self):
        """메시지 전송 처리"""
        try:
            message = self.message_entry.get().strip()
            if message:
                self.process_message(message)
                self.message_entry.delete(0, tk.END)
        except Exception as e:
            print(f"메시지 전송 중 오류 발생: {e}")

    def process_message(self, message):
        """메시지 처리"""
        try:
            if not self.game_state["selected_npc"]:
                self.update_conversation("대화할 NPC를 선택해주세요.", "system")
                return

            self.update_conversation(f"나: {message}", "user")
            # AI 응답 처리 로직 추가
            self.process_npc_response(self.game_state["selected_npc"], message)

        except Exception as e:
            print(f"메시지 처리 중 오류 발생: {e}")

    def update_conversation(self, message, message_type="user"):
        """대화창 업데이트"""
        try:
            if not message or not message.strip():
                return
            
            self.conversation_text.configure(state='normal')
            
            # 메시지 유형에 따른 포맷팅
            if message_type == "user":
                formatted_message = f"👤 나: {message}"
                self.game_state["conversation_history"].append(f"플레이어: {message}")
                # 사용자 메시지 하이라이트 - 파란색
                self.conversation_text.insert('end', formatted_message + "\n\n", ('user',))
                self.conversation_text._textbox.tag_configure('user', foreground='#4DA6FF')
            elif message_type == "npc":
                formatted_message = f"{message}"
                # NPC 메시지 하이라이트 - 녹색
                self.conversation_text.insert('end', formatted_message + "\n\n", ('npc',))
                self.conversation_text._textbox.tag_configure('npc', foreground='#66CC99')
                # NPC 대화는 process_npc_response에서 대화 기록에 추가됨
            elif message_type == "npc_full":
                # 대사, 어투, 속마음, 행동을 포함한 전체 응답
                formatted_message = message
                # 하이라이트 적용 - 녹색
                self.conversation_text.insert('end', formatted_message + "\n\n", ('npc_full',))
                self.conversation_text._textbox.tag_configure('npc_full', foreground='#66CC99')
                # 대화 기록에는 process_npc_response에서 대사만 추가
            elif message_type == "system":
                formatted_message = f"🔧 {message}"
                # 시스템 메시지 하이라이트 - 회색
                self.conversation_text.insert('end', formatted_message + "\n\n", ('system',))
                self.conversation_text._textbox.tag_configure('system', foreground='#AAAAAA')
            else:
                formatted_message = message
                # 기본 메시지 스타일
                self.conversation_text.insert('end', formatted_message + "\n\n")
            
            self.conversation_text.configure(state='disabled')
            self.conversation_text.see('end')
            
            # UI 업데이트 강제
            self.conversation_text.update()
            
        except Exception as e:
            print(f"❌ 대화창 업데이트 오류: {e}")

    def process_npc_response(self, npc_name, user_message):
        try:
            # dialogue.txt 파일 로드
            dialogue_template = self.data_manager.load_dialogue_template()
            if not dialogue_template:
                print("❌ 대화 템플릿 로드 실패")
                self.update_conversation("대화 템플릿을 불러올 수 없습니다.", "system")
                return

            # 현재 감정 상태 로드
            current_emotions = self.data_manager.get_current_emotions(npc_name)
            
            # 감정 상태를 문자열로 변환
            emotion_lines = []
            for emotion, value in current_emotions.items():
                emotion_kr = self.emotion_names.get(emotion, emotion)
                emotion_lines.append(f"{emotion_kr}: {value}%")
            emotion_state = "\n".join(emotion_lines)
            
            # 대화 기록 문자열로 변환
            conversation_history = self.game_state["conversation_history"][-5:] if self.game_state["conversation_history"] else []
            conversation_history_text = "\n".join(conversation_history)
            
            # 현재 위치 정보 가져오기
            current_location = self.game_state.get('current_location', '알 수 없음')
            location_description = f"{current_location}"
            
            # 현재 시간과 이벤트 설정 (필요에 따라 수정)
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            current_event = "좀비 아포칼립스 상황에서 생존 중"
            
            # 현재 상황 설명 생성
            current_npcs = self.data_manager.get_location_npcs(current_location)
            npc_count = len(current_npcs)
            
            # NPC 정보 섹션 생성
            npc_info = self.data_manager.get_npc_data(npc_name)
            npc_info_sections = ""
            if npc_info:
                npc_info_sections = f"이름: {npc_name}\n"
                # persona가 core_info 내부에 있는 경우 처리
                if 'core_info' in npc_info and 'persona' in npc_info['core_info']:
                    persona = npc_info['core_info']['persona']
                    if 'personality_rules' in persona:
                        npc_info_sections += f"성격: {persona['personality_rules']}\n"
                    if 'speech_style' in persona:
                        npc_info_sections += f"말투: {persona['speech_style']}\n"
            
            # 플레이어 정보 (필요에 따라 수정)
            player_name = "플레이어"
            player_rel_emotional_state = "정상"
            
            # dialogue.txt 템플릿에 전달할 데이터 준비
            prompt_data = {
                "npc_name": npc_name,
                "current_emotions": current_emotions,
                "emotion_state": emotion_state,
                "conversation_history_text": conversation_history_text,
                "current_location": current_location,
                "location_description": location_description,
                "current_time": current_time,
                "current_event": current_event,
                "player_name": player_name,
                "player_rel_emotional_state": player_rel_emotional_state,
                "player_message": user_message,
                "npc_count": npc_count,
                "npc_info_sections": npc_info_sections
            }

            # 안전한 템플릿 포맷팅 함수
            def safe_format(template, data):
                # 모든 포맷 필드를 추출
                import re
                fields = re.findall(r'\{([^}]+)\}', template)
                
                # 각 필드를 안전하게 대체
                result = template
                for field in fields:
                    placeholder = '{' + field + '}'
                    if field in data and data[field] is not None:
                        result = result.replace(placeholder, str(data[field]))
                    else:
                        result = result.replace(placeholder, "")
                
                return result
            
            # 대화 프롬프트 포맷팅
            try:
                dialogue_prompt = safe_format(dialogue_template, prompt_data)
            except Exception as e:
                print(f"❌ 대화 프롬프트 포맷팅 오류: {e}")
                self.update_conversation("대화 프롬프트 생성 중 오류가 발생했습니다.", "system")
                return

            def generate_response():
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        # 응답 생성 중임을 표시
                        if retry_count == 0:  # 첫 시도에만 표시
                            self.root.after(0, lambda: self.update_conversation(f"{npc_name}이(가) 응답 중...", "system"))
                        
                        # AI 응답 생성
                        ai_response = self.ai_model.generate_text(dialogue_prompt)
                        print(f"📝 AI 응답:\n{ai_response}")  # 디버깅용
                        
                        # 유효한 응답인지 확인
                        if not ai_response or not self.extract_response_part(ai_response, "대사"):
                            print(f"⚠️ 유효하지 않은 응답, 재시도 {retry_count+1}/{max_retries}")
                            retry_count += 1
                            continue

                        def update_ui():
                            try:
                                # NPC 응답 텍스트 추출
                                speech = self.extract_response_part(ai_response, "대사")
                                action = self.extract_response_part(ai_response, "행동")
                                inner_thought = self.extract_response_part(ai_response, "속마음")
                                
                                # 대화창에 표시할 응답 구성 - 더 간결하게 표시
                                formatted_response = f"{npc_name}: {speech or '...'}"
                                
                                if action:
                                    formatted_response += f"\n[{action}]"
                                
                                if inner_thought:
                                    formatted_response += f"\n(속마음: {inner_thought})"
                                
                                # 대화창에 표시
                                self.update_conversation(formatted_response, "npc_full")
                                
                                # 대화 기록에는 대사만 추가
                                if speech:
                                    self.game_state["conversation_history"].append(f"{npc_name}: {speech}")
                                
                                # 감정 상태 변화 분석 및 업데이트
                                emotion_changes = self.data_manager.analyze_and_update_emotions(
                                    npc_name, user_message, speech or "", inner_thought or ""
                                )
                                
                                # 감정 패널 업데이트
                                self.update_emotion_panel()
                                
                                # 감정 변화 패널 업데이트
                                self.update_emotion_change_panel(emotion_changes, npc_name)
                                
                                # 감정 상태 파일 저장
                                npc_number = self.get_npc_number(npc_name)
                                current_emotions = self.data_manager.get_current_emotions(npc_name)
                                self.save_emotion_state_to_file(npc_name, npc_number, current_emotions)
                                
                                print("✅ 대화 응답 처리 완료")

                            except Exception as e:
                                print(f"❌ UI 업데이트 중 오류: {e}")
                                traceback.print_exc()  # 자세한 오류 출력
                                self.update_conversation("응답 처리 중 오류가 발생했습니다.", "system")

                        self.root.after(0, update_ui)
                        return True  # 성공적으로 응답 생성

                    except Exception as e:
                        print(f"❌ 응답 생성 중 오류: {e}")
                        retry_count += 1
                        time.sleep(1)  # 오류 발생 시 잠시 대기
                
                # 최대 재시도 횟수를 초과한 경우
                if retry_count >= max_retries:
                    self.root.after(0, lambda: self.update_conversation(
                        f"{npc_name}이(가) 응답하지 않습니다. 다시 시도해주세요.", "system"))
                    return False
            
            threading.Thread(target=generate_response, daemon=True).start()

        except Exception as e:
            print(f"❌ NPC 응답 처리 중 오류: {e}")
            traceback.print_exc()  # 자세한 오류 출력
            self.update_conversation("NPC 응답 처리 중 오류가 발생했습니다.", "system")

    def generate_dialogue_prompt(self, npc_name, user_message):
        """대화 프롬프트 생성"""
        try:
            # 현재 감정 상태 로드
            current_emotions = self.data_manager.get_current_emotions(npc_name)
            if not current_emotions:
                print("감정 상태를 불러올 수 없습니다.")
                return None

            # 감정 상태를 문자열로 변환
            emotion_lines = []
            for emotion, value in current_emotions.items():
                emotion_kr = self.emotion_names.get(emotion, emotion)
                emotion_lines.append(f"{emotion_kr}: {value}%")
            emotion_state = "\n".join(emotion_lines)

            # 대화 기록 가져오기
            conversation_history = self.game_state.get("conversation_history", [])
            recent_history = conversation_history[-5:] if conversation_history else []
            conversation_text = "\n".join(recent_history)

            # 프롬프트 생성
            prompt = f"""# NPC 대화 생성

## NPC 정보
이름: {npc_name}
현재 위치: {self.game_state.get('current_location', '알 수 없음')}

## 현재 감정 상태
{emotion_state}

## 최근 대화 내역
{conversation_text}

## 플레이어의 말
"{user_message}"

## 응답 형식
다음 JSON 형식과 함께 NPC 응답을 제공하세요:

```json
{{
  "final_emotions": {{
    // 현재 감정 상태 (변화 적용 후)
    "trust": "80",
    "intimacy": "65",
    // 다른 감정들...
  }},
  "emotion_changes": {{
    // 변화된 감정: [이전값, 새값, 변화 이유]
    "trust": [75, 80, "플레이어가 솔직히 말해줘서 신뢰가 상승"],
    "intimacy": [60, 65, "대화를 통해 친밀감이 조금 상승"]
  }}
}}
```

그 다음 아래 형식으로 NPC의 행동과 대화를 작성하세요:

대사: (NPC가 짧고 간결하게 말하는 내용, 두 문장 이내로 제한)
행동: (NPC의 간단한 행동 묘사, 한 문장으로 제한)
속마음: (NPC의 내면 생각, 한 문장으로 제한)

주의사항:
1. 현재 감정 상태를 반영하여 응답을 생성하세요.
2. 응답은 매우 간결하고 명확해야 합니다. 불필요한 설명이나 반복은 피하세요.
3. 대사는 두 문장 이내로, 행동과 속마음은 각각 한 문장으로 제한하세요.
4. 감정 변화 이유는 짧고 구체적으로 작성하세요.
5. 문체는 간결하고 자연스러운 대화체를 사용하세요."""

            print(f"✅ 프롬프트 생성 완료")
            return prompt

        except Exception as e:
            print(f"❌ 대화 프롬프트 생성 중 오류 발생: {e}")
            return None

    def quit_game(self):
        """게임 종료"""
        try:
            if messagebox.askokcancel("종료", "게임을 종료하시겠습니까?"):
                # 감정 상태 초기화
                self.data_manager.reset_emotion_files()
                # 창 종료
                self.root.destroy()
        except Exception as e:
            print(f"게임 종료 중 오류 발생: {e}")
            self.root.destroy()

    def play_location_music(self, location):
        try:
            # pygame 초기화 확인 및 재초기화 (더 자세한 에러 메시지 추가)
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
                print("✅ pygame 믹서 초기화 성공")
            except Exception as e:
                print(f"❌ pygame 믹서 초기화 실패: {e}")
                self.update_conversation("음악 플레이어 초기화에 실패했습니다.", "system")
                return
            
            # 현재 실행 파일의 디렉토리 경로 가져오기
            current_dir = os.path.dirname(os.path.abspath(__file__))
            print(f"🔍 현재 디렉토리: {current_dir}")
            
            # 위치에 따른 음악 파일 매핑
            location_to_music = {
                "운동장": "music1.mp3",
                "과학실": "music2.mp3",
                "도서관": "music1.mp3",
                "복도": "music2.mp3"
            }
            
            # 위치에 맞는 음악 파일 선택
            music_file = location_to_music.get(location, "music1.mp3")
            
            # 다양한 경로 시도
            possible_paths = [
                os.path.join(current_dir, "music", music_file),  # 현재 디렉토리 기준 상대 경로
                os.path.join("music", music_file),               # 단순 상대 경로
                os.path.abspath(os.path.join("music", music_file)),  # 절대 경로
                music_file                                      # 파일명만
            ]
            
            # 음악 파일 찾기
            music_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    music_path = path
                    print(f"✅ 음악 파일 발견: {path}")
                    break
                
            if not music_path:
                print("❌ 모든 경로에서 음악 파일을 찾을 수 없음")
                # music 폴더 확인 및 생성
                music_dir = os.path.join(current_dir, "music")
                if not os.path.exists(music_dir):
                    try:
                        os.makedirs(music_dir, exist_ok=True)
                        print(f"📂 music 폴더 생성됨: {music_dir}")
                        self.update_conversation("음악 파일이 없어 재생되지 않습니다. 'music' 폴더에 음악 파일을 추가해주세요.", "system")
                    except Exception as make_e:
                        print(f"❌ music 폴더 생성 실패: {make_e}")
                else:
                    # 폴더는 있지만 파일이 없는 경우
                    print(f"✅ 음악 폴더는 존재함: {music_dir}")
                    try:
                        files = os.listdir(music_dir)
                        if files:
                            print(f"📋 음악 폴더 내 파일 목록: {files}")
                            # 다른 가능한 음악 파일 찾기
                            for file in files:
                                if file.endswith('.mp3') or file.endswith('.wav'):
                                    music_path = os.path.join(music_dir, file)
                                    print(f"🎵 대체 음악 파일 사용: {file}")
                                    break
                        else:
                            print("📂 음악 폴더가 비어 있습니다.")
                            self.update_conversation("음악 폴더가 비어 있어 음악이 재생되지 않습니다.", "system")
                    except Exception as folder_e:
                        print(f"❌ 음악 폴더 내용 읽기 실패: {folder_e}")
                
                if not music_path:
                    return
            
            # 이전 음악 중지
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            
            # 음악 로드 및 재생
            try:
                pygame.mixer.music.load(music_path)
                # 볼륨 슬라이더가 있으면 그 값을 사용, 없으면 기본값
                volume = self.volume_slider.get() / 100.0 if hasattr(self, 'volume_slider') else 1.0
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play(-1)  # -1은 무한 반복
                
                # 음소거 상태면 볼륨 0으로 설정
                if hasattr(self, 'is_muted') and self.is_muted:
                    pygame.mixer.music.set_volume(0.0)
                
                # 재생 확인
                if pygame.mixer.music.get_busy():
                    print(f"✅ 음악 재생 성공: {music_file}, 볼륨: {pygame.mixer.music.get_volume()}")
                    # self.update_conversation(f"현재 재생중: {os.path.basename(music_path)}", "system")
                else:
                    print(f"⚠️ 음악이 로드되었지만 재생 중이지 않음")
                
            except pygame.error as pe:
                print(f"❌ pygame 음악 로드/재생 오류: {pe}")
                self.update_conversation("음악 파일 형식이 지원되지 않거나 손상되었습니다.", "system")
            except Exception as e:
                print(f"❌ 음악 재생 중 오류 발생: {e}")
                self.update_conversation("음악 재생 중 오류가 발생했습니다.", "system")
            
        except Exception as e:
            print(f"❌ 음악 재생 함수 실행 중 오류 발생: {e}")
            self.update_conversation("음악 시스템에 문제가 발생했습니다.", "system")

    def update_emotion_state(self, npc_name, emotions):
        """감정 상태 업데이트 및 저장"""
        try:
            # NPC 번호 찾기
            npc_number = None
            for i in range(1, 6):
                json_path = f"data/student_{i}.json"
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("name") == npc_name:
                            npc_number = str(i)
                            break
        
            if npc_number:
                # emotion*.txt 파일에 감정 상태 저장
                emotion_file = f"emotion/emotion{npc_number}.txt"
                try:
                    # 감정 상태를 JSON 형식으로 저장
                    with open(emotion_file, 'w', encoding='utf-8') as f:
                        json.dump(emotions, f, ensure_ascii=False, indent=2)
                    print(f"✅ 감정 상태 저장 완료: {emotion_file}")
                    
                    # 게임 상태 업데이트
                    self.game_state["current_emotions"][npc_name] = emotions
                    
                    # 감정 패널 업데이트
                    self.update_emotion_panel()
                    
                except Exception as e:
                    print(f"❌ 감정 상태 저장 중 오류 발생: {e}")
            else:
                print(f"⚠️ NPC 번호를 찾을 수 없습니다: {npc_name}")
            
        except Exception as e:
            print(f"❌ 감정 상태 업데이트 중 오류 발생: {e}")

    def process_ai_response(self, response_text):
        """AI 응답 처리"""
        try:
            # JSON 응답에서 감정 상태 추출
            response_data = json.loads(response_text)
            if "최종감정상태" in response_data:
                emotions = response_data["최종감정상태"]
                selected_npc = self.game_state.get("selected_npc")
                if selected_npc:
                    self.update_emotion_state(selected_npc, emotions)
            
            # 나머지 응답 처리 로직...
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 중 오류 발생: {e}")
        except Exception as e:
            print(f"❌ AI 응답 처리 중 오류 발생: {e}")

    def update_emotion_change_panel(self, emotion_changes, npc_name):
        """감정 변화 패널 업데이트"""
        try:
            self.emotion_change_text.configure(state='normal')
            self.emotion_change_text.delete('1.0', 'end')
            
            if not emotion_changes:
                self.emotion_change_text.insert('end', "감정 변화 없음", ('no_change',))
                self.emotion_change_text._textbox.tag_configure('no_change', foreground='#AAAAAA', font=("Malgun Gothic", 12))
            else:
                # 제목 추가
                self.emotion_change_text.insert('end', f"{npc_name}의 감정 변화\n\n", ('title',))
                self.emotion_change_text._textbox.tag_configure('title', font=("Malgun Gothic", 14, "bold"))
                
                for emotion, (old_value, new_value) in emotion_changes.items():
                    if emotion in self.emotion_names:
                        # 한글 감정 이름 가져오기
                        emotion_kr = self.emotion_names.get(emotion, emotion)
                        
                        # 변화 계산
                        change = new_value - old_value
                        
                        # 변화 방향에 따른 화살표와 색상 태그
                        if change > 0:
                            arrow = "↑"
                            tag = 'increase'
                            direction = "증가"
                        elif change < 0:
                            arrow = "↓"
                            tag = 'decrease'
                            direction = "감소"
                        else:
                            arrow = "→"
                            tag = 'neutral'
                            direction = "유지"
                        
                        # 변화 크기에 따른 표현
                        if abs(change) >= 8:
                            level = "매우 크게"
                        elif abs(change) >= 5:
                            level = "크게"
                        elif abs(change) >= 3:
                            level = "상당히"
                        elif abs(change) >= 1:
                            level = "조금"
                        else:
                            level = "약간"
                        
                        # 감정 이름 먼저 삽입
                        self.emotion_change_text.insert('end', f"{emotion_kr}: ", ('emotion_name',))
                        self.emotion_change_text._textbox.tag_configure('emotion_name', font=("Malgun Gothic", 12, "bold"))
                        
                        # 변화된 수치 삽입
                        change_text = f"{old_value:.1f}% {arrow} {new_value:.1f}% ({level} {direction})"
                        self.emotion_change_text.insert('end', change_text + "\n\n", (tag,))
                        
                # 태그 설정
                self.emotion_change_text._textbox.tag_configure('increase', foreground='#FF6B6B')
                self.emotion_change_text._textbox.tag_configure('decrease', foreground='#6B6BFF')
                self.emotion_change_text._textbox.tag_configure('neutral', foreground='#FFFFFF')
                
                # 감정 변화 요약
                summary = f"총 {len(emotion_changes)}개 감정 변화"
                self.emotion_change_text.insert('end', summary, ('summary',))
                self.emotion_change_text._textbox.tag_configure('summary', font=("Malgun Gothic", 12, "bold"), foreground='#CCCCCC')
                        
            self.emotion_change_text.configure(state='disabled')
            
        except Exception as e:
            print(f"❌ 감정 변화 패널 업데이트 중 오류 발생: {e}")
            traceback.print_exc()

    def extract_response_part(self, response_text, part_label):
        """응답 텍스트에서 특정 부분(대사, 행동, 속마음 등) 추출"""
        try:
            if not response_text:
                return None
                
            # Python 딕셔너리 형태로 응답이 온 경우 처리
            try:
                # JSON 형태인지 확인하고 파싱
                import json
                response_dict = json.loads(response_text)
                if isinstance(response_dict, dict) and part_label in response_dict:
                    return response_dict[part_label]
            except:
                pass  # JSON이 아닌 경우 계속 진행
                
            # 여러 가지 정규 표현식 패턴 시도
            patterns = [
                # 일반적인 패턴: "대사: 내용"
                rf"{part_label}\s*[:：]\s*(.*?)(?=(?:\n\w+\s*[:：])|$)",
                
                # 콜론 없이 줄바꿈만 사용하는 패턴: "대사\n내용"
                rf"{part_label}\s*\n(.*?)(?=(?:\n\w+\s*(?:\n|\s*[:：]))|$)",
                
                # 따옴표를 사용하는 패턴: "대사": "내용"
                rf'"{part_label}"\s*:\s*"(.*?)"(?=,|\}}|$)',
                
                # 큰 제목 형식: "## 대사\n내용"
                rf"#{1,6}\s*{part_label}\s*\n(.*?)(?=(?:\n#{1,6}\s*\w+)|$)",
                
                # 다양한 구분자 패턴: "대사 - 내용" 또는 "대사 > 내용"
                rf"{part_label}\s*[-–—>]\s*(.*?)(?=(?:\n\w+\s*[-–—>])|$)"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response_text, re.DOTALL)
                if match:
                    return match.group(1).strip()
            
            # 마지막 수단: 키워드 이후의 모든 텍스트를 검색
            keyword_start = re.search(rf"\b{part_label}\b", response_text)
            if keyword_start:
                # 키워드 이후의 텍스트에서 다음 키워드 찾기
                next_keywords = ["대사", "행동", "속마음", "어투"]
                end_positions = []
                for keyword in next_keywords:
                    if keyword != part_label:
                        next_keyword = re.search(rf"\b{keyword}\b", response_text[keyword_start.end():])
                        if next_keyword:
                            end_positions.append(keyword_start.end() + next_keyword.start())
                
                if end_positions:
                    # 가장 가까운 다음 키워드까지의 텍스트
                    relevant_text = response_text[keyword_start.end():min(end_positions)]
                else:
                    # 다음 키워드가 없으면 끝까지
                    relevant_text = response_text[keyword_start.end():]
                
                # 텍스트 정리 (콜론 제거, 첫 줄의 공백 제거 등)
                relevant_text = re.sub(r'^[:\s]+', '', relevant_text).strip()
                return relevant_text if relevant_text else None
                
            return None
        except Exception as e:
            print(f"응답 파싱 오류: {e}")
            traceback.print_exc()
            return None

    def estimate_emotion_change_reason(self, emotion, change, npc_name, conversation_history):
        # 여기에 감정 변화 이유를 추정하는 로직을 구현해야 합니다.
        # 현재는 간단하게 변화 크기에 따라 이유를 추정하는 로직을 구현했습니다.
        if abs(change) >= 10:
            return f"{emotion}이(가) 크게 변했습니다."
        elif abs(change) >= 5:
            return f"{emotion}이(가) 상당히 변했습니다."
        elif abs(change) >= 2:
            return f"{emotion}이(가) 조금 변했습니다."
        else:
            return f"{emotion}이(가) 약간 변했습니다."

    def save_emotion_state_to_file(self, npc_name, npc_number, emotions):
        """감정 상태를 파일에 저장"""
        try:
            # 감정 파일 경로
            emotion_file = f"emotion/emotion{npc_number}.txt"
            
            # 디렉토리 확인 및 생성
            os.makedirs(os.path.dirname(emotion_file), exist_ok=True)
            
            # 감정 상태를 JSON 형식으로 저장
            with open(emotion_file, 'w', encoding='utf-8') as f:
                json.dump(emotions, f, ensure_ascii=False, indent=2)
            
            print(f"✅ {npc_name}의 감정 상태 저장 완료: {emotion_file}")
            
        except Exception as e:
            print(f"❌ 감정 상태 파일 저장 중 오류 발생: {e}")

    def change_location(self, new_location):
        """위치 변경"""
        try:
            if new_location in ["복도", "과학실", "도서관", "운동장"]:
                # 이전 위치
                old_location = self.game_state["current_location"]
                
                # 이미 해당 위치에 있다면 무시
                if new_location == old_location:
                    return
                
                # 게임 상태 업데이트
                self.game_state["current_location"] = new_location
                
                # 위치 레이블 업데이트
                self.location_label.configure(text=f"현재 위치: {new_location}")
                
                # 위치 이미지 업데이트
                self.update_location_image(new_location)
                
                # NPC 목록 업데이트
                self.update_npc_list()
                
                # 배경음악 변경
                self.play_location_music(new_location)
                
                # 메시지 표시
                self.update_conversation(f"{old_location}에서 {new_location}으로 이동했습니다.", "system")
                
                print(f"✅ 위치 변경 완료: {new_location}")
                
            else:
                print(f"❌ 유효하지 않은 위치: {new_location}")
                
        except Exception as e:
            print(f"❌ 위치 변경 중 오류 발생: {e}")

    def update_map(self):
        """맵 상태 업데이트"""
        try:
            if not self.map_loaded or not self.map_canvas:
                # 맵이 로드되지 않았거나 캔버스가 없으면 종료
                self.root.after(100, self.update_map)
                return
                
            # 캔버스 초기화
            self.map_canvas.delete("player")
            self.map_canvas.delete("npc")
            
            # 플레이어 그리기
            self.map_canvas.create_oval(
                self.player_pos[0] - self.player_size[0]//2,
                self.player_pos[1] - self.player_size[1]//2,
                self.player_pos[0] + self.player_size[0]//2,
                self.player_pos[1] + self.player_size[1]//2,
                fill="blue", outline="white", width=2, tags="player"
            )
            
            # NPC 그리기
            for npc_name, pos in self.npc_positions.items():
                self.map_canvas.create_oval(
                    pos[0] - 15, pos[1] - 15,
                    pos[0] + 15, pos[1] + 15,
                    fill="red", outline="yellow", width=2, tags="npc"
                )
                self.map_canvas.create_text(
                    pos[0], pos[1] - 25,
                    text=npc_name, fill="white", font=("맑은 고딕", 10), tags="npc"
                )
            
            # 주기적으로 업데이트
            self.root.after(100, self.update_map)
            
        except Exception as e:
            print(f"❌ 맵 업데이트 중 오류 발생: {e}")
            self.root.after(100, self.update_map)  # 오류가 발생해도 계속 업데이트
            
    def handle_key_press(self, event):
        """키 입력 처리"""
        try:
            if not self.map_loaded:
                return
                
            move_speed = 10
            old_pos = self.player_pos.copy()
            
            # 키 입력에 따라 이동
            if event.keysym == "Up" or event.keysym == "w":
                self.player_pos[1] -= move_speed
            elif event.keysym == "Down" or event.keysym == "s":
                self.player_pos[1] += move_speed
            elif event.keysym == "Left" or event.keysym == "a":
                self.player_pos[0] -= move_speed
            elif event.keysym == "Right" or event.keysym == "d":
                self.player_pos[0] += move_speed
                
            # 이동 가능 영역 확인
            if not self.is_position_walkable(self.player_pos):
                self.player_pos = old_pos  # 이동 불가능하면 이전 위치로 복귀
                
            # 맵 경계 처리
            self.player_pos[0] = max(15, min(self.map_size[0] - 15, self.player_pos[0]))
            self.player_pos[1] = max(15, min(self.map_size[1] - 15, self.player_pos[1]))
            
            # NPC와의 상호작용 확인
            self.check_npc_interaction()
            
        except Exception as e:
            print(f"❌ 키 입력 처리 중 오류 발생: {e}")
            
    def check_npc_interaction(self):
        """NPC와의 상호작용 확인"""
        try:
            for npc_name, pos in self.npc_positions.items():
                # 플레이어와 NPC 사이의 거리 계산
                distance = ((self.player_pos[0] - pos[0])**2 + (self.player_pos[1] - pos[1])**2)**0.5
                
                # 일정 거리 이내면 상호작용
                if distance < 30:  # 상호작용 거리
                    # 이미 현재 NPC가 선택되어 있는지 확인
                    current_npc = self.game_state.get("current_npc")
                    if current_npc != npc_name:
                        # NPC 선택
                        self.select_npc(npc_name)
                        # 상호작용 메시지 표시
                        self.update_conversation(f"{npc_name}과(와) 대화를 시작합니다.", "system")
                    break
                    
        except Exception as e:
            print(f"❌ NPC 상호작용 확인 중 오류 발생: {e}")
            
    def place_npcs_randomly(self):
        """NPC를 맵에 랜덤으로 배치"""
        try:
            # 현재 맵의 NPC 목록 가져오기
            location_npcs = self.data_manager.get_location_npcs(self.current_map)
            
            # 위치 딕셔너리 초기화
            self.npc_positions = {}
            
            # 최대 5명의 NPC만 배치
            npc_count = min(5, len(location_npcs))
            chosen_npcs = random.sample(location_npcs, npc_count) if len(location_npcs) > npc_count else location_npcs
            
            # 각 NPC 랜덤 위치에 배치
            for npc_name in chosen_npcs:
                # 유효한 위치 찾기
                valid_position = False
                attempts = 0
                
                while not valid_position and attempts < 20:
                    # 랜덤 위치 생성
                    x = random.randint(50, self.map_size[0] - 50)
                    y = random.randint(50, self.map_size[1] - 50)
                    
                    # 이동 가능 영역인지 확인
                    if self.is_position_walkable([x, y]):
                        # 다른 NPC와 겹치는지 확인
                        overlap = False
                        for _, pos in self.npc_positions.items():
                            if ((x - pos[0])**2 + (y - pos[1])**2)**0.5 < 50:
                                overlap = True
                                break
                                
                        if not overlap:
                            valid_position = True
                            self.npc_positions[npc_name] = [x, y]
                            
                    attempts += 1
                    
                # 유효한 위치를 찾지 못한 경우, 강제로 위치 지정
                if not valid_position:
                    self.npc_positions[npc_name] = [
                        random.randint(50, self.map_size[0] - 50),
                        random.randint(50, self.map_size[1] - 50)
                    ]
            
            print(f"✅ NPC 배치 완료: {len(self.npc_positions)}명")
            
        except Exception as e:
            print(f"❌ NPC 배치 중 오류 발생: {e}")
            traceback.print_exc()
            
    def load_walkable_areas(self, map_name):
        """이동 가능 영역 로드"""
        try:
            # 맵 설정 파일 경로
            map_config_path = f"maps/{map_name}_config.json"
            
            # 맵 설정 파일이 있는지 확인
            if os.path.exists(map_config_path):
                # 파일에서 이동 가능 영역 로드
                with open(map_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.walkable_areas = config.get("walkable_areas", [])
                    # 시작 위치 설정
                    start_pos = config.get("start_position", [100, 100])
                    self.player_pos = start_pos
            else:
                # 설정 파일이 없으면 전체 영역을 이동 가능으로 설정
                print(f"⚠️ 맵 설정 파일을 찾을 수 없어 전체 영역을 이동 가능으로 설정합니다: {map_config_path}")
                self.walkable_areas = [[10, 10, self.map_size[0] - 10, self.map_size[1] - 10]]
                
        except Exception as e:
            print(f"❌ 이동 가능 영역 로드 중 오류 발생: {e}")
            # 오류 발생 시 전체 영역을 이동 가능으로 설정
            self.walkable_areas = [[10, 10, self.map_size[0] - 10, self.map_size[1] - 10]]
            
    def is_position_walkable(self, pos):
        """위치가 이동 가능한지 확인"""
        try:
            # 이동 가능 영역이 설정되지 않았으면 모든 위치가 이동 가능
            if not self.walkable_areas:
                return True
                
            # 모든 이동 가능 영역에 대해 확인
            for area in self.walkable_areas:
                # 영역 내에 있는지 확인
                if area[0] <= pos[0] <= area[2] and area[1] <= pos[1] <= area[3]:
                    return True
                    
            return False
            
        except Exception as e:
            print(f"❌ 이동 가능 영역 확인 중 오류 발생: {e}")
            return True  # 오류 발생 시 이동 가능으로 처리

# ------------------------------
# 4. 애플리케이션 실행
# ------------------------------
if __name__ == "__main__":
    # Custom Tkinter 애플리케이션 설정
    ctk.set_appearance_mode("dark")  # 다크 모드
    ctk.set_default_color_theme("blue")  # 블루 테마
    
    # 루트 윈도우 생성
    root = ctk.CTk()
    root.title("좀비 아포칼립스 RPG - Enhanced UI")
    root.geometry("1200x800")
    
    # 게임 인스턴스 생성
    game = GameWindow(root)
    
    # 테스트용 예시
    game.update_images(npc_name="강현준", location="복도")
    
    root.mainloop()