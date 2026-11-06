.PHONY: all clean

all: Bericht_Webanwendungen.pdf

autoren.tex: ../.env sync_autoren.py
	python3 sync_autoren.py

Bericht_Webanwendungen.pdf: Bericht_Webanwendungen.tex autoren.tex
	latexmk -pdf -pdflatex="pdflatex -interaction=nonstopmode" -use-make Bericht_Webanwendungen.tex

clean:
	latexmk -CA
	rm -f autoren.tex
