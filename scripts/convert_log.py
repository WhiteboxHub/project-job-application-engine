import sys

def convert_log(filename):
    try:
        with open(filename, 'r', encoding='utf-16-le') as f:
            content = f.read()
        
        outfile = filename.replace('.log', '.txt')
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully converted {filename} to {outfile}")
    except Exception as e:
        print(f"Error converting {filename}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        convert_log(sys.argv[1])
    else:
        print("Usage: python convert_log.py <filename>")
