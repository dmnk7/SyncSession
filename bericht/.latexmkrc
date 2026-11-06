# Liest ../.env, bevor pdflatex das Deckblatt setzt.
$pdflatex = 'python3 sync_autoren.py && pdflatex -interaction=nonstopmode %O %S';
