const flipper = document.getElementById("pages");
const pageFlip = new St.PageFlip(flipper, {width:395, height:705, showCover: true});

pageFlip.loadFromHTML(document.querySelectorAll(".leaf"));
document.querySelectorAll('nav a').forEach((i) => {

    i.addEventListener("click", (e) => {
        pn = Number(e.target.innerText);
        pageFlip.flip(pn,'top');
    });

});
