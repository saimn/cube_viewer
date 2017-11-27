from setuptools import setup, find_packages

setup(
    name='cube_viewer',
    version='0.1',
    packages=find_packages(),
    zip_safe=False,
    install_requires=['numpy', 'astropy', 'mpdaf', 'pyqtgraph'],
    entry_points={
        'gui_scripts': [
            'cube_viewer = cube_viewer:main',
        ]
    },
)
