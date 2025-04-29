# 调整导入顺序和代码结构
import os
import re
import fnmatch
import math
import sqlite3
import logging
from typing import Optional
import ffmpeg
import flet as ft

# 常量定义
ID_PATTERN = re.compile(r'([a-zA-Z]{2,5})(-|00)?(\d{2,5})')  # 恢复常量定义
VIDEO_EXTENSIONS = ('*.mp4', '*.mkv', '*.avi')               # 恢复常量定义

# 日志配置（必须在函数定义前初始化）
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('avid.log', mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 工具函数 --------------------------------------------------
def find_video_files(directory: str) -> list:
    """查找目录下的视频文件"""
    return [
        os.path.join(root, filename)
        for root, _, files in os.walk(directory)
        for ext in VIDEO_EXTENSIONS
        for filename in fnmatch.filter(files, ext)
    ]

def find_id(input_string: str) -> str:
    """从文件名中提取电影ID"""
    # 需要移除的字符串列表
    DOMAINS_TO_REMOVE = ["hhd800.com", "hjd2048.com", "zzpp01.com", "zzpp06.com", "bo99.tv","zzpp03.com","bbs2048.org","big2048.com","avav55.xyz","ddr91","aavv121.com","dioguitar23","yjs521","zzpp08.com"]
    # 使用正则表达式一次性替换所有域名
    pattern = "|".join(map(re.escape, DOMAINS_TO_REMOVE))
    string = re.sub(pattern, "", input_string)
    match = ID_PATTERN.search(string)
    return f"{match.group(1).upper()}-{match.group(3)}" if match else input_string

def get_video_info(video_path: str, logger) -> Optional[dict]:
    """获取视频文件的元数据信息"""
    try:
        if not os.path.exists(video_path):
            logger.warning("文件不存在: %s", video_path)
            return None
            
        probe = ffmpeg.probe(video_path)
        video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)

        # 使用字典的 get 方法避免 KeyError
        format_section = probe.get('format', {})
        # 添加时长处理逻辑
        duration_str = format_section.get('duration', '0')
        try:
            duration = float(duration_str)
        except (ValueError, TypeError):
            duration = 0.0

        # 添加比特率获取逻辑
        bit_rate = 0
        if video_info:
            try:
                # 尝试从视频流获取比特率
                bit_rate = int(video_info.get('bit_rate', 0)) 
            except (TypeError, ValueError):
                # 尝试从format段获取总比特率
                bit_rate = int(format_section.get('bit_rate', 0))

        info = {
            'video_duration': duration,  # 使用已定义的duration变量
            'video_codec_name': video_info.get('codec_name') if video_info else None,
            'video_width': int(video_info.get('width', 0)) if video_info else 0,
            'video_height': int(video_info.get('height', 0)) if video_info else 0,
            'file_size': int(format_section.get('size', 0)),
            'file_format': format_section.get('format_name'),
            'video_bitrate': bit_rate  # 确保该字段始终存在
        }
        return info
    except ffmpeg.Error as e:
        logger.error("FFmpeg探测错误: %s", str(e))
    except FileNotFoundError:
        logger.error("文件未找到: %s", video_path)
    return None

def sec_to_hms(seconds: float) -> tuple:
    """
    将秒数转换为时分秒格式
    返回：(小时, 分钟, 秒) 元组
    """
    # 添加类型检查
    if not isinstance(seconds, (int, float)):
        seconds = 0.0
    hours = int(seconds // 3600)  # 转换为整数
    minutes = int((seconds % 3600) // 60)  # 保持整数转换
    seconds = math.ceil(seconds % 60)
    if seconds == 60:
        minutes += 1
        seconds = 0

    return (hours, minutes, seconds)
# 主逻辑函数 --------------------------------------------------
def update_row(e, row, page):
    """更新行数据"""
    new_value = e.control.value
    if e.control == row.cells[1].content:  # 电影ID列
        row.cells[2].content.value = new_value + os.path.splitext(row.cells[0].content.value)[1]
    page.update()

def rename_read(
    directory: str,
    data_table: ft.DataTable,
    page: ft.Page,
    show_message: ft.Text
) -> None:
    """读取目录视频文件并构建重命名表格"""
    show_message.value =f"正在读取目录{directory}下文件..."
    logger.info(f"正在读取目录{directory}下文件...")
    page.update()
    video_files = find_video_files(directory)
    sn = 1
    all_rows = []
    if data_table:
        all_rows.clear()
        for file_path in video_files:
            show_message.value = f"正在处理： {file_path} 处理进度 {sn}/{len(video_files)}"
            page.update()
            info = get_video_info(file_path,logger)
            if info is None:
                logger.warning(f"无法获取文件信息: {file_path}")
                continue
                
            # 添加filename定义（从file_path提取文件名）
            filename = os.path.basename(file_path)  # ← 新增此行
            main_name, filename_extension = os.path.splitext(filename)
            movie_id = find_id(filename)
            # 添加-C后缀判断
            if main_name.endswith("-UC"):
                suffix = "-C"
            elif main_name.endswith("-C"):
                suffix = "-C"
            else:
                suffix = ""

            new_name = f"{movie_id}{suffix}{filename_extension}"
            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(sn)),
                    ft.DataCell(ft.Text(filename)),
                    ft.DataCell(ft.TextField(value=movie_id, on_change=lambda e: update_row(e, row, page))),
                    ft.DataCell(ft.TextField(value=new_name, on_change=lambda e: update_row(e, row, page))),
                    ft.DataCell(ft.Text(f"{int(info['file_size']) / 1024 / 1024:.2f} MB")),
                    ft.DataCell(ft.Text(info['file_format'])),
                ]
            )
            sn += 1
            all_rows.append(row)
    data_table.rows = all_rows
    show_message.value = "文件读取完成"
    page.update()
    logger.info("文件读取完成")

def query_read(
    directory: str,
    data_table: ft.DataTable,
    page: ft.Page,
    show_message: ft.Text    
) -> None:
    """查询并显示目录中的视频文件信息。
    
    参数:
    - directory: 目录路径。
    - data_table: 数据表对象。
    - page: 页面对象。
    """
    def select_changed(e,page):
        if e.control.selected:
            e.control.selected = False
        else:
            e.control.selected = True
        page.update()

    def open_videoinf(e, page, file_path):

        # 从事件对象获取行数据
        row = e.control
        # 提取并保存视频的片名
        video_name = row.cells[1].content.value
        # 提取并保存视频的唯一标识符
        id = row.cells[2].content.value
        # 提取并保存视频的尺寸信息
        size = row.cells[3].content.value
        # 提取并保存视频的分辨率信息
        video_resolution = row.cells[4].content.value
        # 提取并保存视频的时长信息
        duration = row.cells[5].content.value
        # 提取并保存视频的编解码器信息
        video_codec = row.cells[6].content.value
        # 提取并保存视频的比特率信息
        video_bitrate = row.cells[7].content.value
        #提取是否有中文字幕
        chs = row.cells[8].content.value
        conn = sqlite3.connect('avid.db')
        res=query_id(id,conn)
        conn.close()
        all_rows=[]
        all_rows.append(
            ft.DataRow(cells=[           
                ft.DataCell(ft.Text('当前视频')),
                ft.DataCell(ft.Text(video_name)),
                ft.DataCell(ft.Text(id)),
                ft.DataCell(ft.Text(size)),
                ft.DataCell(ft.Text(video_resolution)),
                ft.DataCell(ft.Text(duration)),
                ft.DataCell(ft.Text(video_codec)),
                ft.DataCell(ft.Text(video_bitrate)),
                ft.DataCell(ft.Text(chs)),
                ]  # ← 确保所有值都用ft.Text包装
            ))
        for i in res:
            row=ft.DataRow(cells=[           
                ft.DataCell(ft.Text(str(sn))),  # 确保数值转换为字符串
                ft.DataCell(ft.Text(str(i[2]))),
                ft.DataCell(ft.Text(str(i[1]))),
                ft.DataCell(ft.Text(f"{float(i[3]):.2f} MB")),
                ft.DataCell(ft.Text(str(i[4]))),
                ft.DataCell(ft.Text(str(i[5]))),
                ft.DataCell(ft.Text(str(i[6]))),
                ft.DataCell(ft.Text(str(i[7]))),
                ft.DataCell(ft.Text('是' if i[8]==True else '否')),
                ]  # ← 确保所有值都用ft.Text包装
            )
            all_rows.append(row)
        
        # 确保对话框内容使用Container控件包装
        dlg = ft.AlertDialog(
            title=ft.Text("视频文件详情"),
            content=ft.Container(
                content=ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("序号")),  # 必须使用DataColumn实例
                        ft.DataColumn(ft.Text("文件名")),
                        ft.DataColumn(ft.Text("电影ID")),
                        ft.DataColumn(ft.Text("文件大小")),
                        ft.DataColumn(ft.Text("分辨率")),
                        ft.DataColumn(ft.Text("时长")),
                        ft.DataColumn(ft.Text("视频编码")),
                        ft.DataColumn(ft.Text("视频码率(Kbps)")),
                        ft.DataColumn(ft.Text("是否中文字幕")),
                    ],
                    rows=all_rows
                ),
                padding=10
            ),
            modal=True,
            actions=[
                ft.TextButton("关闭", on_click=lambda e: page.close(dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.open(dlg)

    try:
        conn = sqlite3.connect('avid.db')
    except Exception as e:
        logger.error(f"数据库查询错误: {e}")
    else:
        logger.info("数据库连接成功")

    video_files = find_video_files(directory)
    sn = 1
    all_rows = []
    if data_table:
        all_rows.clear()
        # 在query_read函数中修改数据行创建部分
        for file_path in video_files:
            show_message.value = f"正在处理： {file_path} 处理进度 {sn}/{len(video_files)}"
            page.update()
            info = get_video_info(file_path,logger)
            if info is None:
                logger.warning(f"无法获取文件信息: {file_path}")
                continue
                
            filename = os.path.basename(file_path)
            main_name=os.path.splitext(filename)[0]
            movie_id = find_id(filename)
            id_exist = query_id(movie_id,conn)
            if id_exist:
                display_alert = ft.Text('有')
                row_selected = False
            else:
                display_alert = ft.Text('无')
                row_selected = True
            hms = sec_to_hms(info['video_duration'])
            row = ft.DataRow(
                cells=[
                        ft.DataCell(ft.Text(sn)),
                        ft.DataCell(ft.Text(filename)),  # ← 使用已定义的filename变量
                        ft.DataCell(ft.Text(movie_id)),
                        ft.DataCell(ft.Text(f"{int(info['file_size']) / 1024 / 1024:.2f} MB")),
                        ft.DataCell(ft.Text(str(info['video_width']) + "x" + str(info['video_height']))),
                        ft.DataCell(ft.Text(f"{hms[0]:02d}:{hms[1]:02d}:{hms[2]:02d}")),  # 修改为格式化字符串
                        ft.DataCell(ft.Text(info['video_codec_name'])),
                        ft.DataCell(ft.Text(str(info['video_bitrate']))),
                        ft.DataCell(ft.Text("是" if main_name.endswith("-C") else "否")),
                        ft.DataCell(display_alert)
                ],
                on_select_changed=lambda e: select_changed(e,page),
                on_long_press=lambda e, path=file_path: open_videoinf(e, page, path),  # 添加路径参数
                color=ft.Colors.YELLOW_50 if id_exist else ft.Colors.WHITE,
                selected=row_selected
            )  # 确保闭合括号正确对齐
            sn += 1  # ← 修正缩进层级（4个空格）
            all_rows.append(row)  # ← 修正缩进层级（4个空格）
            
    data_table.rows = all_rows
    conn.close()
    show_message.value = "数据更新完成"
    page.update()
    logger.info("数据更新完成")


def write_db(data_table: ft.DataTable, page: ft.Page, msg: ft.Text, logger) -> None:
    """将数据写入数据库"""
    try:
        conn = sqlite3.connect('avid.db')
        cursor = conn.cursor()
        # 同步更新表结构
        cursor.execute('''CREATE TABLE IF NOT EXISTS videos
                        (sn INTEGER PRIMARY KEY AUTOINCREMENT,
                        id TEXT, filename TEXT, size REAL, 
                        resolution TEXT, duration REAL, 
                        codec TEXT, bitrate INTEGER,
                        chs BOOLEAN)''')  # 同步表结构
        success = 0
        failure = 0
        # 遍历数据行插入记录
        for row in data_table.rows:
            if not row.selected:
                continue
            # 从数据行提取信息
            movie_id = row.cells[2].content.value  # 电影ID列
            filename = row.cells[1].content.value  # 文件名列
            size_mb = float(row.cells[3].content.value.split()[0])  # 文件大小(MB)
            resolution = row.cells[4].content.value  # 分辨率
            duration_str = row.cells[5].content.value  # 时长(H:M:S)
            codec = row.cells[6].content.value  # 视频编码
            bitrate = int(row.cells[7].content.value)  # 视频码率
            chs = True if row.cells[8].content.value == '是' else False  # 是否中文字幕
            
            cursor.execute('''SELECT * FROM videos WHERE id = ?''', (movie_id,))
            select_res =  cursor.fetchall()
            if select_res:
                logger.info(f"{movie_id}数据已存在，更新")
                cursor.execute('''UPDATE videos SET filename =?, size =?, resolution =?, duration =?, codec =?, bitrate =?, chs =? WHERE id =?''',
                            (filename, size_mb, resolution, duration_str, codec, bitrate, chs, movie_id))
            else:
                logger.info(f"{movie_id}数据不存在，新增")            
                # 执行INSERT操作
                cursor.execute('''INSERT INTO videos 
                                (id, filename, size, resolution, duration, codec, bitrate, chs)
                                VALUES (?,?,?,?,?,?,?,?)''',
                            (movie_id, filename, size_mb, resolution, 
                            duration_str, codec, bitrate, chs))  
            success += 1
        conn.commit()
        msg.value = f"共{len(data_table.rows)}记录，成功写入{success}条记录"
        logger.info(f"共{len(data_table.rows)}记录，成功写入{success}条记录")
    except Exception as e:
        logger.error(f"数据库写入失败: {str(e)}")
        msg.value = "数据库写入失败"
    finally:
        conn.close()
    page.update()

def query_id(movie_id: str, conn: sqlite3.Connection) -> list:
    """
    查询数据库中的电影记录
    返回:
        包含匹配记录的列表（按时间倒序排列）
    """
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS videos
                        (sn INTEGER PRIMARY KEY AUTOINCREMENT,
                        id TEXT, filename TEXT, size REAL, 
                        resolution TEXT, duration REAL, 
                        codec TEXT, bitrate INTEGER,
                        chs BOOLEAN)''')  # 新增布尔字段
        cursor.execute("SELECT * FROM videos WHERE id=?", (movie_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error("数据库查询错误: %s", str(e))
        return []

def rename(data_table: ft.DataTable, path_field: ft.TextField, page: ft.Page, msg: ft.Text, logger) -> None:
    """执行批量重命名操作"""
    success = 0
    failure = 0
    base_dir = path_field.value
    
    for row in data_table.rows:
        old_name = os.path.join(base_dir, row.cells[1].content.value)
        new_name = os.path.join(base_dir, row.cells[3].content.value)
        if new_name == old_name:
            continue
        try:            
            os.rename(old_name, new_name)

        except Exception as e:
            logger.error(f"重命名失败: {str(e)}")
            failure += 1
        else:
            logger.info(f"{old_name}重命名为{new_name}")
            success += 1
            
    msg.value = f"操作完成：成功 {success} 条，失败 {failure} 条"
    page.update()

def main(page: ft.Page):
    """
    主函数。
    
    初始化UI并处理用户交互。
    """


    page.title = "路径选择示例"
    page.vertical_alignment = ft.CrossAxisAlignment.CENTER
    page.window.width = 1350
    page.fonts = {
        "微软雅黑": "Microsoft YaHei"
    }
    page.theme = ft.Theme(font_family="微软雅黑")
    rename_txt_path = ft.TextField(label="选择路径", read_only=True, expand=True)
    query_txt_path = ft.TextField(label="选择路径", read_only=True, expand=True)
    rename_path = r''
    query_path = r''
    show_message = ft.Text( size=16, color=ft.Colors.DEEP_ORANGE)

    def select_rename_folder(e):
        nonlocal rename_path
        rename_path = e.path
        rename_txt_path.value = rename_path
        page.update()

    def select_query_folder(e):
        nonlocal query_path
        query_path = e.path
        query_txt_path.value = query_path
        page.update()

    rename_picker = ft.FilePicker(on_result=select_rename_folder)
    query_picker = ft.FilePicker(on_result=select_query_folder)
    page.overlay.extend([rename_picker, query_picker])

    rename_data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("序号", width=30),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("原文件名", width=280),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("电影ID", width=150),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("新文件名", width=200),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("文件大小", width=100),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("文件格式", width=350),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        rows=[],
    )
    query_data_table = ft.DataTable(

        columns=[
            ft.DataColumn(ft.Text("序号"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("文件名"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("电影ID"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("文件大小"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("分辨率"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("时长"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("视频编码"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("视频码率(Kbps)"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("中文字幕"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            ft.DataColumn(ft.Text("存在"),heading_row_alignment=ft.CrossAxisAlignment.CENTER),
            
        ],
        rows=[],
        show_checkbox_column=True,
        divider_thickness=0
    )

    # 创建一个提升型按钮用于选择要重命名的文件夹
    btn_rename_folder = ft.ElevatedButton("选择文件夹", on_click=lambda _: rename_picker.get_directory_path())
    # 创建一个提升型按钮用于选择要查询的文件夹
    btn_query_folder = ft.ElevatedButton("选择文件夹", on_click=lambda _: query_picker.get_directory_path())
    # 创建一个提升型按钮，用于读取重命名操作的相关数据
    btn_rename_read = ft.ElevatedButton("读取", on_click=lambda _: rename_read(rename_txt_path.value, rename_data_table, page,show_message))
    # 创建一个提升型按钮，用于读取查询操作的相关数据
    btn_query_read = ft.ElevatedButton("读取", on_click=lambda _: query_read(query_txt_path.value, query_data_table, page,show_message))
    # 创建一个提升型按钮，用于执行重命名操作
    btn_rename = ft.ElevatedButton("重命名", on_click=lambda _: rename(rename_data_table, rename_txt_path, page,show_message,logger))
    btn_store_database = ft.ElevatedButton("写入数据库", on_click=lambda _: write_db(query_data_table, page,show_message,logger))
    tab = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="重命名",
                content=ft.Column([
                    ft.Row([
                        ft.Text("文件重命名", size=24)]
                        ),
                    ft.Row(
                        [rename_txt_path, btn_rename_folder, btn_rename_read, btn_rename], 
                        alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(
                        ft.ListView(
                            [rename_data_table],
                            expand=True,
                            auto_scroll=True
                        ),
                        padding=10,
                        expand=True
                    ),
                ])
            ),
            ft.Tab(
                text="数据",
                content=ft.Column([
                    ft.Text("数据查询", size=24),
                    ft.Row(
                        [query_txt_path, btn_query_folder, btn_query_read, btn_store_database],
                        alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(
                        ft.ListView(
                            [query_data_table],
                            expand=True,
                            auto_scroll=True
                        ),
                        padding=10,
                        expand=True
                    ),
                ]),
            ),
        ],
        expand=1,
    )
    page.add(tab,
             ft.Container(show_message, alignment=ft.alignment.center)
             )

ft.app(target=main)