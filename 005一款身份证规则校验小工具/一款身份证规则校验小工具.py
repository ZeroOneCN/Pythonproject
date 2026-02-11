import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QFileDialog)
from PyQt6.QtGui import QFont, QRegularExpressionValidator
from PyQt6.QtCore import Qt, QRegularExpression
import datetime
import time


class IDValidatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.coeff = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        self.check = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
        # 省市级别地区码
        self.area_codes = {
            '11': '北京市', '12': '天津市', '13': '河北省', '14': '山西省',
            '15': '内蒙古自治区', '21': '辽宁省', '22': '吉林省', '23': '黑龙江省',
            '31': '上海市', '32': '江苏省', '33': '浙江省', '34': '安徽省',
            '35': '福建省', '36': '江西省', '37': '山东省', '41': '河南省',
            '42': '湖北省', '43': '湖南省', '44': '广东省', '45': '广西壮族自治区',
            '46': '海南省', '50': '重庆市', '51': '四川省', '52': '贵州省',
            '53': '云南省', '54': '西藏自治区', '61': '陕西省', '62': '甘肃省',
            '63': '青海省', '64': '宁夏回族自治区', '65': '新疆维吾尔自治区',
            '71': '台湾省', '81': '香港特别行政区', '82': '澳门特别行政区'
        }
        self.initUI()

    def initUI(self):
        self.setWindowTitle('身份证验证器')
        self.setGeometry(100, 100, 600, 400)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        songti_font = QFont('SimSun', 12)

        # 输入区
        input_layout = QHBoxLayout()

        self.id_label = QLabel('请输入身份证号：')
        self.id_label.setFont(songti_font)
        input_layout.addWidget(self.id_label)

        self.id_input = QLineEdit()
        self.id_input.setFont(songti_font)
        self.id_input.setMinimumWidth(300)
        self.id_input.setMaxLength(18)
        self.id_input.setPlaceholderText('请输入18位身份证号码')
        regex = QRegularExpression('[0-9Xx]{0,18}')
        validator = QRegularExpressionValidator(regex)
        self.id_input.setValidator(validator)
        self.id_input.returnPressed.connect(self.verify_single_id)
        input_layout.addWidget(self.id_input)

        self.verify_btn = QPushButton('验证')
        self.verify_btn.setFont(songti_font)
        self.verify_btn.clicked.connect(self.verify_single_id)
        input_layout.addWidget(self.verify_btn)

        self.batch_btn = QPushButton('批量验证')
        self.batch_btn.setFont(songti_font)
        self.batch_btn.clicked.connect(self.verify_batch)
        input_layout.addWidget(self.batch_btn)

        layout.addLayout(input_layout)

        # 提示信息
        self.tip_label = QLabel('批量验证文件格式：*.txt文件，每行一个身份证号')
        self.tip_label.setFont(QFont('SimSun', 10))
        self.tip_label.setStyleSheet("color: #666;")
        layout.addWidget(self.tip_label)

        # 输出区
        self.output_text = QTextEdit()
        self.output_text.setFont(songti_font)
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        # 退出按钮
        self.exit_btn = QPushButton('退出')
        self.exit_btn.setFont(songti_font)
        self.exit_btn.clicked.connect(self.close)
        layout.addWidget(self.exit_btn)

        # 蓝色主题
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f8ff;
            }
            QPushButton {
                background-color: #4682b4;
                color: white;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4169e1;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #b0c4de;
                border-radius: 3px;
                background-color: white;
            }
            QTextEdit {
                border: 1px solid #b0c4de;
                border-radius: 3px;
                background-color: white;
            }
        """)

    def verify_id(self, ID):
        today = datetime.datetime.now().strftime('%Y%m%d')
        year = time.localtime(time.time())[0]

        if len(ID) != 18:
            return '身份证长度应为18位，请重新输入。'

        if not ID[0:17].isdigit():
            return '身份证前17位应全部为数字，请重新输入！'

        if int(ID[6:10]) not in range(1900, year + 1):
            return f'出生年份{ID[6:10]}错误，应介于[1900--{year}]年之间，请重新输入！'

        if int(ID[6:14]) > int(today):
            return f'出生日期[{ID[6:14]}]不应晚于当前日期[{today}]，请重新输入！'

        try:
            birth_date = time.strptime(ID[6:14], "%Y%m%d")
            birth_str = time.strftime("%Y年%m月%d日", birth_date)
            tmp = 0
            for i in range(17):
                tmp += int(ID[i]) * self.coeff[i]
            mod = tmp % 11
            sex = '女' if int(ID[-2]) % 2 == 0 else '男'
            area = self.area_codes.get(ID[0:2], '未知地区')

            if str(self.check[mod]).upper() == ID[-1].upper():
                return f'********此身份证号校验无误********\n地区：{area}\n出生日期：{birth_str}\n性别：{sex}'
            else:
                return f'身份证末位校验码"{ID[-1]}"不正确（应为"{self.check[mod]}"）'

        except ValueError:
            return f'出生日期[{ID[6:14]}:年月日]不是合法的格式，请重新输入！'

    def verify_single_id(self):
        ID = self.id_input.text().strip()
        if not ID:
            self.output_text.clear()
            self.output_text.append('请输入身份证号')
            return
        self.output_text.clear()
        result = self.verify_id(ID)
        self.output_text.append(result)

    def verify_batch(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择身份证号码文件", "", "Text Files (*.txt)")
        if file_name:
            self.output_text.clear()
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    ids = [line.strip() for line in file if line.strip()]
                    if not ids:
                        self.output_text.append('文件中没有有效的身份证号')
                        return
                    for ID in ids:
                        result = self.verify_id(ID)
                        self.output_text.append(f'身份证号: {ID}\n{result}\n{"-" * 40}')
            except Exception as e:
                self.output_text.append(f'读取文件时出错：{str(e)}')


def main():
    app = QApplication(sys.argv)
    window = IDValidatorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
