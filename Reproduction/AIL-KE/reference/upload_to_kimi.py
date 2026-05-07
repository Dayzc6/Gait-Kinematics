import os
from pathlib import Path
from openai import OpenAI


def upload_pdf_to_kimi(pdf_path: str, api_key: str = None) -> dict:
    """
    上传 PDF 文件到 Kimi API
    
    Args:
        pdf_path: PDF 文件路径
        api_key: Kimi API Key，如果为 None 则从环境变量 MOONSHOT_API_KEY 读取
    
    Returns:
        上传后的文件对象信息
    """
    if api_key is None:
        api_key = os.environ.get("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError("请提供 api_key 或设置环境变量 MOONSHOT_API_KEY")
    
    client = OpenAI(
        api_key='sk-kimi-ELORqcoTXMh0XqnEvHr4DW3ahLCAxMggCof1cZnPlcZYJcDxWftEGdWfLVr2TKcU',
        base_url="https://api.moonshot.cn/v1",
    )
    
    file_object = client.files.create(
        file=Path(r'E:\code\3D-position\Reproduction\AIL-KE\reference'), 
        purpose="file-extract"
    )
    
    return {
        "id": file_object.id,
        "filename": file_object.filename,
        "bytes": file_object.bytes,
        "purpose": file_object.purpose,
        "status": file_object.status,
    }


def upload_all_pdfs_in_reference(api_key: str = None) -> list:
    """
    上传 reference 目录下的所有 PDF 文件
    
    Returns:
        上传成功的文件信息列表
    """
    reference_dir = Path(__file__).parent
    pdf_files = list(reference_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("reference 目录下没有找到 PDF 文件")
        return []
    
    results = []
    for pdf_file in pdf_files:
        print(f"正在上传: {pdf_file.name}")
        try:
            result = upload_pdf_to_kimi(str(pdf_file), api_key)
            results.append(result)
            print(f"✓ 上传成功: {result['id']}")
        except Exception as e:
            print(f"✗ 上传失败: {pdf_file.name} - {e}")
    
    return results


if __name__ == "__main__":
    # 示例：上传 reference 目录下的所有 PDF
    uploaded_files = upload_all_pdfs_in_reference()
    
    print("\n上传结果汇总:")
    for file_info in uploaded_files:
        print(f"  - {file_info['filename']}: {file_info['id']}")
