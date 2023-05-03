const trans = true;
const MyInfo = {
	Name: "Howe",
	Age: 22
};
if(trans){
	MyInfo["Name"] = "Piper Howe"
}
else{
	MyInfo["Name"] = "James Howe"
}

Array.from(document.getElementsByClassName("Name")).forEach(elem => (elem.textContent = MyInfo["Name"]));
for (const [key, value] of Object.entries(MyInfo)) {
  console.log(key, value);
}