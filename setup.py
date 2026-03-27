from setuptools import setup, find_packages
import os

setup(
    name='yuclaw',
    version='1.2.0',
    description='YUCLAW — Open Financial Intelligence Platform. Real backtests. ZKP audit. Local AI.',
    long_description=open('README_PACKAGE.md').read() if os.path.exists('README_PACKAGE.md') else '',
    long_description_content_type='text/markdown',
    author='YuClawLab',
    url='https://github.com/YuClawLab/yuclaw-brain',
    packages=find_packages(),
    install_requires=[
        'yfinance>=0.2.0',
        'pandas>=2.0.0',
        'numpy>=1.24.0',
        'requests>=2.28.0',
        'fastapi>=0.100.0',
        'uvicorn>=0.20.0',
        'rich>=13.0.0',
    ],
    entry_points={
        'console_scripts': [
            'yuclaw=yuclaw.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Office/Business :: Financial :: Investment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.10',
    ],
    python_requires='>=3.10',
)
