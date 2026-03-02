import qrcode
import argparse


def generate_qrcode(text, filename="qrcode.png"):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    print(f"二维码已生成并保存为: {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成二维码")
    parser.add_argument("text", help="要生成二维码的文本内容")
    parser.add_argument(
        "-f", "--filename", default="qrcode.png", help="输出文件名 (默认: qrcode.png)"
    )
    args = parser.parse_args()

    generate_qrcode(args.text, args.filename)
