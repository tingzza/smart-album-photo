
from imagededup.methods import PHash
from imagededup.utils import plot_duplicates
import matplotlib.pyplot as plt
import multiprocessing

def main():
    phasher = PHash()
    image_dir = 'D:/MyFile/grade1/CV2/proj/photo'
    
    # Generate encodings for all images in an image directory
    encodings = phasher.encode_images(image_dir=image_dir)
    
    # Find duplicates using the generated encodings
    duplicates = phasher.find_duplicates(encoding_map=encodings)
    
    # plot duplicates obtained for a given file using the duplicates dictionary
    for filename, duplicate_files in duplicates.items():
        if duplicate_files:  # 只处理有重复的组
            print(f"Plotting duplicates for: {filename}")
            # 绘制当前组的重复图片（每组一行）
            plot_duplicates(
                image_dir=image_dir,  # 使用修正后的路径
                duplicate_map=duplicates,
                filename=filename
            )
            # 显示图形（避免重叠）
            plt.show()

if __name__ == '__main__':
    # Windows 系统可能需要 freeze_support()
    #multiprocessing.freeze_support()  # 如果打包成exe则需要，否则可注释
    main()