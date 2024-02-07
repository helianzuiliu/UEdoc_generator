cp /root/output/CppAPI-HTML.tgz /root/
cp /root/output/UEdoc_generator.py /root/

cd /root 

mkdir CppAPI
mv CppAPI-HTML.tgz /root/CppAPI/
cd CppAPI

tar -zxvf CppAPI-HTML.tgz

rm CppAPI-HTML.tgz

cd /root 
python UEdoc_generator.py -n "UE5" ./CppAPI UE5.docset

tar -zcvf UE5_doc.tgz UE5.docset/

mv UE5_doc.tgz /root/output/
