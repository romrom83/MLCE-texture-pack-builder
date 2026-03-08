**CURRENTLY BROKEN FUUUCK**

# MLCE-texture-pack-builder
Simple python script to make custom texture packs for Minecraft Legacy Console Edition

I've provided an example pack in the release, keep the file structure the same or the game will crash  
the game should accept x32 textures and more, But the script that generate them will be added in a future commit

just drag the source folder on the script and move what's inside the output in a subfolder of your DLC folder

Example of what the pack should look like at the end:  
https://github.com/ContinuedOak/Legacy-Edition-Resource-Packs  
thanks so much to ContinuedOak for providing this pack!

What will be added next:
- Support for the following files: Languages.loc Colours.col Media.arc
- Java to LCE texture pack automatic converter (currently you have to stitch your texture atlas yourself)

Those files are used to override any text color and UI in the game, that's also why I'd be more inclined to call them ressource packs and not texture packs!

If you dont trust the exe you can compile the .py yourself, you just need pillow and tkinter

